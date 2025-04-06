import logging
import mimetypes
import os
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Iterator, Callable

from lmpack import formatting
from lmpack.dir_tree import create_ascii_tree
from lmpack.ignores import FilePatternMatcher

log = logging.getLogger(__name__)

DEFAULT_FILE_TEMPLATE = Template(
    dedent(
        """
        --- FILE START ---
        Path: ${file_path_rel}
        ```${file_syntax}
        ${file_content}
        ```
        --- FILE END ---
        """
    )
)

DEFAULT_FILE_NO_CONTENT_TEMPLATE = Template(
    dedent(
        """
        --- FILE START ---
        Path: ${file_path_rel}
        (Content Skipped)
        --- FILE END ---
        """
    )
)

DEFAULT_FILE_BINARY_CONTENT_TEMPLATE = Template(
    dedent(
        """
        --- FILE START ---
        Path: ${file_path_rel}
        Size: ${file_size} bytes
        (Binary content)
        --- FILE END ---
        """
    )
)

DEFAULT_FILE_ERROR_TEMPLATE = Template(
    dedent(
        """
        --- FILE START ---
        Path: ${file_path_rel}
        Error reading file: ${error}
        --- FILE END ---
        """
    )
)


def is_binary(file_path: Path) -> bool:
    """
    Check if a file is binary.
    """
    # 1. First check mime type
    mime = mimetypes.guess_type(file_path)

    if mime and mime[0] is not None:
        return mime[0].startswith("text") is False

    # 2. If mime type is not conclusive, read the first 1024 bytes
    with open(file_path, "rb") as f:
        chunk = f.read(1024)
        if b'\0' in chunk:
            return True

    return False


@dataclass
class LmPacker:
    index_path: Path

    file_ignores: FilePatternMatcher = FilePatternMatcher()
    content_ignores: FilePatternMatcher = FilePatternMatcher()

    include_matcher: FilePatternMatcher = FilePatternMatcher()

    file_template: Template = DEFAULT_FILE_TEMPLATE
    file_error_template: Template | None = DEFAULT_FILE_ERROR_TEMPLATE
    file_binary_content_template: Template | None = DEFAULT_FILE_BINARY_CONTENT_TEMPLATE

    display_path_normalizer: Callable[[Path], str] = formatting.to_disp_path

    COUNT_IGNORES = {
        "default": 0,
        "gitignore": 0,
        "include_patterns": 0,
    }

    COUNT_FILES = {
        "processed": 0,
        "included": 0,
        "included_no_content": 0,
    }

    def create_ascii_tree(self) -> str:
        """
        Create an ASCII representation of the directory tree.
        """
        return create_ascii_tree(self.index_path, self.file_ignores, base_path=self.index_path)

    def write_file_contents(self, io: StringIO) -> None:
        """
        Write the contents of the files to the provided StringIO object.
        """
        for content in self.iter_file_contents():
            io.write(content)

    def iter_file_contents(self) -> Iterator[str]:
        index_path = self.index_path

        for root, _, files in os.walk(index_path):
            for file in files:
                file_path_abs = Path(root, file).resolve()
                file_path_rel = file_path_abs.relative_to(index_path)

                self.COUNT_FILES["processed"] += 1

                # Check if the file is excluded
                if self.file_ignores.is_match(file_path_rel):
                    self.COUNT_IGNORES["default"] += 1
                    continue

                # Only if include patterns not empty, check for inclusion
                if len(self.include_matcher):
                    if not self.include_matcher.is_match(file_path_rel):
                        self.COUNT_IGNORES["include_patterns"] += 1
                        continue

                # Check if the file content should be ignored
                if self.content_ignores.is_match(file_path_rel):
                    self.COUNT_FILES["included_no_content"] += 1
                    self.COUNT_FILES["included"] += 1
                    continue

                # normalize for display
                file_path_rel_disp = self.display_path_normalizer(file_path_rel)

                file_ext = os.path.splitext(file)[1].lower()
                file_syntax = formatting.get_codeblock_language(file_ext)

                # Check if the file is binary
                if is_binary(file_path_abs):
                    if self.file_binary_content_template:
                        content = self.file_binary_content_template.safe_substitute(
                            file_path_rel=file_path_rel_disp,
                            file_size=os.path.getsize(file_path_abs),
                        )
                        self.COUNT_FILES["included"] += 1
                        yield content
                    continue

                try:
                    with open(file_path_abs, "r", encoding="utf-8-sig") as f:
                        file_content = f.read()

                    content = self.file_template.safe_substitute(
                        file_path_rel=file_path_rel_disp,
                        file_syntax=file_syntax,
                        file_content=file_content,
                    )

                    self.COUNT_FILES["included"] += 1

                    yield content
                except Exception as e:
                    log.warning(f"Error reading file {file_path_rel}: {e}")
                    content = self.file_error_template.safe_substitute(
                        file_path_rel=file_path_rel_disp,
                        error=str(e),
                    )

                    yield content
