import logging
import mimetypes
import os
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Iterator, Callable, Dict

from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from lmpack import formatting

from lmpack.ignores import FilePatternMatcher
from lmpack.nodes import FileSystemNode, FileNode, DirectoryNode  # New import
from lmpack.tokenizers import TokenizerBackend, NullTokenizerBackend  # New import

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
        if mime[0].startswith("text"):
            return False

        if mime[0].startswith("image"):
            return True

        if mime[0].startswith("application"):
            # Some are binary, like icons, but some are not
            if mime[0] == "application/octet-stream":
                return True
            # Check for specific application types that are not binary
            if mime[0] in ["application/json", "application/xml"]:
                return False

    # 2. If mime type is not conclusive, read the first 1024 bytes
    with open(file_path, "rb") as f:
        chunk = f.read(1024)
        if b"\0" in chunk:
            return True

    return False


@dataclass
class LmPacker:
    index_path: Path
    tokenizer: TokenizerBackend = field(default_factory=NullTokenizerBackend)  # Use tokenizer

    file_ignores: FilePatternMatcher = field(default_factory=FilePatternMatcher)
    content_ignores: FilePatternMatcher = field(default_factory=FilePatternMatcher)
    include_matcher: FilePatternMatcher = field(default_factory=FilePatternMatcher)

    file_template: Template = DEFAULT_FILE_TEMPLATE
    file_error_template: Template | None = DEFAULT_FILE_ERROR_TEMPLATE
    file_binary_content_template: Template | None = DEFAULT_FILE_BINARY_CONTENT_TEMPLATE

    display_path_normalizer: Callable[[Path], str] = formatting.to_disp_path

    # Counters can be moved to main or kept here and reset
    stats: Dict[str, int] = field(
        default_factory=lambda: {
            "files_processed": 0,
            "files_ignored_file_pattern": 0,
            "files_ignored_include_pattern": 0,
            "files_content_skipped": 0,
            "files_binary": 0,
            "files_read_error": 0,
            "files_included_with_content": 0,
            "dirs_processed": 0,
            "dirs_ignored": 0,
        }
    )

    def _reset_stats(self):
        self.stats = {k: 0 for k in self.stats}

    def build_tree(self) -> DirectoryNode:
        """Builds an in-memory representation of the directory structure."""
        self._reset_stats()

        root_node = DirectoryNode(
            path_rel=Path(), name=self.index_path.name, path_abs=self.index_path.resolve()
        )
        dir_map: Dict[Path, DirectoryNode] = {Path("."): root_node}

        for root, dirs, files in os.walk(self.index_path, topdown=True):
            root_abs = Path(root).resolve()
            root_rel = root_abs.relative_to(self.index_path)
            parent_node = dir_map[root_rel]

            # Process directories
            dirs_to_process = []
            for dir_name in sorted(dirs):
                self.stats["dirs_processed"] += 1
                dir_abs = Path(root, dir_name).resolve()
                dir_rel = dir_abs.relative_to(self.index_path)
                dir_node = DirectoryNode(dir_rel, dir_name, dir_abs)

                # Check ignores/includes for the directory itself
                dir_node.is_ignored = self.file_ignores.is_match(dir_rel)
                if len(self.include_matcher) > 0:
                    ...
                    # Include check: matches dir OR any potential child path
                    # dir_node.is_included = self.include_matcher.is_match(dir_rel) or (
                    #     self.include_matcher.is_match(f"{dir_rel}/**")
                    # )  # Heuristic

                if not dir_node.should_process:
                    self.stats["dirs_ignored"] += 1
                    # Prune this directory from os.walk traversal if ignored
                    dirs.remove(dir_name)
                    log.debug(f"Ignoring directory: {dir_rel}")
                    continue  # Don't add to parent or dir_map

                parent_node.add_child(dir_node)
                dir_map[dir_rel] = dir_node
                dirs_to_process.append(dir_name)
            # Update dirs[:] only with those we decided to process
            # Note: Modifying dirs in place is how os.walk pruning works
            dirs[:] = dirs_to_process

            # Process files
            for file_name in sorted(files):
                self.stats["files_processed"] += 1
                file_path_abs = Path(root, file_name).resolve()
                file_path_rel = file_path_abs.relative_to(self.index_path)

                file_node = FileNode(file_path_rel, file_name, file_path_abs)

                # Check file ignores
                if self.file_ignores.is_match(file_path_rel):
                    file_node.is_ignored = True
                    self.stats["files_ignored_file_pattern"] += 1
                    parent_node.add_child(
                        file_node
                    )  # Add even if ignored, for completeness maybe? Or skip? Let's add.
                    log.debug(f"Ignoring file by pattern: {file_path_rel}")
                    continue  # Don't process content/tokens if ignored

                # Check include patterns (only if they exist)
                if len(self.include_matcher) > 0 and not self.include_matcher.is_match(
                    file_path_rel
                ):
                    file_node.is_included = False
                    self.stats["files_ignored_include_pattern"] += 1
                    parent_node.add_child(file_node)  # Add but mark as not included
                    log.debug(f"Ignoring file by include mismatch: {file_path_rel}")
                    continue  # Don't process content/tokens if not included

                # Check content ignores
                if self.content_ignores.is_match(file_path_rel):
                    file_node.content_skipped = True
                    self.stats["files_content_skipped"] += 1
                    log.debug(f"Skipping content for: {file_path_rel}")
                    # Still add the node, token count is 0

                # Check if binary (only if content not skipped)
                if not file_node.content_skipped:
                    try:
                        if is_binary(file_path_abs):
                            file_node.is_binary = True
                            self.stats["files_binary"] += 1
                            log.debug(f"Detected binary file: {file_path_rel}")
                    except Exception as e:
                        log.warning(f"Error checking if binary {file_path_rel}: {e}")
                        file_node.read_error = f"Binary check error: {e}"
                        self.stats["files_read_error"] += 1

                # Calculate tokens (only if text, included, not ignored, content not skipped)
                if (
                    file_node.should_process
                    and not file_node.content_skipped
                    and not file_node.is_binary
                    and file_node.read_error is None
                ):
                    file_node.calculate_tokens(self.tokenizer)  # Reads file temporarily
                    if file_node.read_error:
                        self.stats["files_read_error"] += 1
                    elif file_node.token_count is not None:
                        self.stats["files_included_with_content"] += 1
                else:
                    file_node.token_count = 0  # Ensure token count is 0 if not calculated

                parent_node.add_child(file_node)

        root_node.sort_children()  # Sort the entire tree
        # Trigger calculation and caching of token counts recursively
        _ = root_node.get_total_tokens()
        return root_node

    def create_ascii_tree(self, root_node: DirectoryNode, show_tokens: bool = False) -> str:
        """Creates an ASCII representation of the built directory tree."""
        lines = []

        if show_tokens and isinstance(self.tokenizer, NullTokenizerBackend):
            log.warning("Tokenizer is not set, cannot show token counts.")
            show_tokens = False

        def build_tree_lines(node: FileSystemNode, prefix: str = "", is_last: bool = True):
            # Only add nodes that should be processed
            if not node.should_process:
                return

            # Use the passed 'show_tokens' flag
            token_str = (
                f" ({node.get_total_tokens()} tokens)"
                if show_tokens and node.get_total_tokens() > 0
                else ""
            )

            if isinstance(node, DirectoryNode):
                # Handle root node name display differently
                if node == root_node:
                    connector = ""  # No connector for the root
                    new_prefix = ""
                    lines.append(f"{node.name}{token_str}")
                else:
                    connector = "└── " if is_last else "├── "
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    lines.append(f"{prefix}{connector}{node.name}{token_str}")

                # Process children
                for i, child in enumerate(node.children):
                    build_tree_lines(child, new_prefix, i == len(node.children) - 1)

            elif isinstance(node, FileNode):
                # File node
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{node.name}{token_str}")

        build_tree_lines(root_node)
        return "\n".join(lines)

    def create_rich_tree(self, root_node: DirectoryNode, show_tokens: bool = False) -> Tree:
        """Creates a Rich Tree representation of the built directory tree."""

        if show_tokens and isinstance(self.tokenizer, NullTokenizerBackend):
            log.warning("Tokenizer is not set, cannot show token counts.")
            show_tokens = False

        tree = Tree(
            f":open_file_folder: [link file://{root_node.path_abs}]{escape(root_node.name)}",
            guide_style="bold bright_blue",
        )

        def build_rich_branch(node: FileSystemNode, branch: Tree):
            """Recursively build the Rich branch."""
            # Determine style based on ignored/skipped status
            node_style = ""
            guide_style = "bold bright_blue"  # Default guide style
            if not node.should_process:
                node_style = "dim grey50"
                guide_style = "dim grey50"  # Dim guides for ignored branches
            elif isinstance(node, FileNode) and (
                node.content_skipped or node.is_binary or node.read_error
            ):
                node_style = "dim"  # Dim files with skipped/binary/error content

            # Get token string if applicable
            token_str = ""
            if show_tokens:
                node_tokens = node.get_total_tokens()
                if node_tokens > 0:
                    token_str = f" ({node_tokens:,} tokens)"

            if isinstance(node, DirectoryNode):
                label = Text.from_markup(
                    f":open_file_folder: [link file://{node.path_abs}]{escape(node.name)}"
                )
                label.append(
                    token_str, style="blue" if node.should_process else "dim blue"
                )  # Append token count
                sub_branch = branch.add(label, style=node_style, guide_style=guide_style)
                for child in node.children:
                    build_rich_branch(child, sub_branch)

            elif isinstance(node, FileNode):
                # Icon logic (basic for now)
                icon = "📄 "
                if node.name.endswith(".py"):
                    icon = "🐍 "
                elif node.is_binary:
                    icon = "📦 "
                elif node.read_error:
                    icon = "❓ "
                elif node.content_skipped:
                    icon = "🚫 "

                text_filename = Text(
                    escape(node.name), style="green" if node.should_process else "dim green"
                )
                text_filename.highlight_regex(
                    r"\..*$", "bold red" if node.should_process else "dim bold red"
                )
                text_filename.stylize(f"link file://{node.path_abs}")

                # Append token count (only if tokens > 0 and should process)
                if (
                    show_tokens
                    and node.token_count
                    and node.token_count > 0
                    and node.should_process
                ):
                    text_filename.append(f" ({node.token_count:,} tokens)", "blue")
                elif node.is_binary and not node.read_error:
                    try:
                        file_size = node.path_abs.stat().st_size
                        text_filename.append(f" ({decimal(file_size)})", "dim blue")
                    except Exception as ex:
                        # Ignore stat errors for binary size display
                        log.warning(f"Error getting size for {node.path_abs}: {ex}")
                elif node.read_error:
                    text_filename.append(f" (Error)", "dim red")

                label = Text(icon) + text_filename
                branch.add(label, style=node_style)  # Leaves don't use guide_style

        # Build the tree recursively starting from root's children
        for child in root_node.children:
            build_rich_branch(child, tree)

        return tree

    def iter_formatted_output_blocks(self, root_node: DirectoryNode) -> Iterator[str]:
        """Traverses the built tree and yields formatted output blocks, re-reading files as needed."""

        nodes_to_process: list[FileSystemNode] = [root_node]

        while nodes_to_process:
            current_node = nodes_to_process.pop(0)  # Process in BFS order to match os.walk approx

            if not current_node.should_process:
                continue

            if isinstance(current_node, DirectoryNode):
                # Add children to the queue in their sorted order
                nodes_to_process.extend(current_node.children)

            elif isinstance(current_node, FileNode):
                file_node = current_node
                file_path_rel_disp = self.display_path_normalizer(file_node.path_rel)

                if file_node.content_skipped:
                    # Use the NO_CONTENT template (reuse existing one)
                    yield DEFAULT_FILE_NO_CONTENT_TEMPLATE.safe_substitute(
                        file_path_rel=file_path_rel_disp
                    )
                    continue  # Move to next node

                if file_node.is_binary:
                    if self.file_binary_content_template:
                        yield self.file_binary_content_template.safe_substitute(
                            file_path_rel=file_path_rel_disp,
                            file_size=os.path.getsize(file_node.path_abs),  # Get size again
                        )
                    continue  # Move to next node

                if file_node.read_error:
                    if self.file_error_template:
                        yield self.file_error_template.safe_substitute(
                            file_path_rel=file_path_rel_disp,
                            error=file_node.read_error,
                        )
                    continue  # Move to next node

                # If we reach here, it's a text file needing content
                try:
                    # *** Re-read the file content ***
                    with open(file_node.path_abs, "r", encoding="utf-8-sig") as f:
                        file_content = f.read()

                    file_ext = os.path.splitext(file_node.name)[1].lower()
                    file_syntax = formatting.get_codeblock_language(file_ext)

                    yield self.file_template.safe_substitute(
                        file_path_rel=file_path_rel_disp,
                        file_syntax=file_syntax,
                        file_content=file_content,
                    )
                except Exception as e:
                    # Handle potential error during the second read
                    log.warning(f"Error re-reading file {file_node.path_rel} for output: {e}")
                    if self.file_error_template:
                        yield self.file_error_template.safe_substitute(
                            file_path_rel=file_path_rel_disp,
                            error=f"Output generation error: {e}",
                        )
