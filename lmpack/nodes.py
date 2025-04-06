# lmpack/nodes.py (New File)
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List

from lmpack.tokenizers import TokenizerBackend, NullTokenizerBackend

log = logging.getLogger(__name__)


class FileSystemNode:
    """Base class for nodes in the file system tree."""

    def __init__(self, path_rel: Path, name: str):
        self.path_rel = path_rel
        self.name = name
        self.is_ignored: bool = False  # Ignored by file_ignores?
        self.is_included: bool = True  # Included by include_patterns? (Default True if no includes)

    @property
    def should_process(self) -> bool:
        """Determines if this node should be processed (not ignored and included)."""
        return self.is_included and not self.is_ignored

    def get_total_tokens(self) -> int:
        """Calculates the total token count for this node and its children."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', path_rel='{self.path_rel}')"


class FileNode(FileSystemNode):
    """Represents a file in the file system tree."""

    def __init__(self, path_rel: Path, name: str, path_abs: Path):
        super().__init__(path_rel, name)
        self.path_abs = path_abs
        self.token_count: Optional[int] = None
        self.is_binary: bool = False
        self.content_skipped: bool = False  # Ignored by content_ignores?
        self.read_error: Optional[str] = None

    def calculate_tokens(self, tokenizer: TokenizerBackend):
        """Reads the file (if necessary) and calculates token count."""
        if (
            not self.should_process
            or self.content_skipped
            or self.is_binary
            or self.read_error is not None
        ):
            self.token_count = 0
            return

        if self.token_count is not None:  # Already calculated
            return

        try:
            # Read content only for tokenization
            with open(self.path_abs, "r", encoding="utf-8-sig") as f:
                content = f.read()
            self.token_count = tokenizer.count_tokens(content)
            # Discard content immediately after counting
        except UnicodeDecodeError:
            log.warning(f"UnicodeDecodeError reading {self.path_rel}, treating as binary.")
            self.is_binary = True
            self.token_count = 0
        except Exception as e:
            log.warning(f"Error reading file {self.path_rel} for token count: {e}")
            self.read_error = str(e)
            self.token_count = 0

    def get_total_tokens(self) -> int:
        """Returns the token count for this file if it should be processed."""
        return self.token_count or 0 if self.should_process else 0


class DirectoryNode(FileSystemNode):
    """Represents a directory in the file system tree."""

    def __init__(self, path_rel: Path, name: str, path_abs: Path):
        # Use '.' for root directory display relative path
        super().__init__(path_rel if path_rel else Path('.'), name)
        self.path_abs = path_abs # Store absolute path
        self.children: List[FileSystemNode] = []
        self._cached_token_count: Optional[int] = None

    def add_child(self, node: FileSystemNode):
        """Adds a child node to this directory."""
        self.children.append(node)

    def get_total_tokens(self) -> int:
        """Recursively calculates the total token count for the directory."""
        if not self.should_process:
            return 0
        # Calculate if not cached
        if self._cached_token_count is None:
            self._cached_token_count = sum(child.get_total_tokens() for child in self.children)
        return self._cached_token_count

    def sort_children(self):
        """Sorts children (directories first), then recursively."""
        # Sort directories first, then files, alphabetically by name
        self.children.sort(key=lambda x: (not isinstance(x, DirectoryNode), x.name.lower()))
        # Recursively sort children of subdirectories
        for child in self.children:
            if isinstance(child, DirectoryNode):
                child.sort_children()

    def __repr__(self) -> str:
        # Limit children in repr for clarity
        child_repr = ", ".join(repr(c) for c in self.children[:3])
        if len(self.children) > 3:
            child_repr += f", ... ({len(self.children)} total)"
        return f"{super().__repr__()[:-1]}, children=[{child_repr}])"
