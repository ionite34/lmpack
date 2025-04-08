import fnmatch
import logging
import os
from pathlib import Path
from typing import Iterable

from py_walk import get_parser_from_file
from py_walk.models import Parser

log = logging.getLogger(__name__)


class FilePatternMatcher:
    def __init__(self):
        self.parsers: list[Parser] = []
        self.path_ignores: list[str] = []

    def scan_add_pattern_files(self, directory: Path, file_patterns: list[str]):
        """
        Scan the provided directory for ignore files and add them to the IgnoreMatcher.
        """
        for path in directory.glob("*"):
            if path.is_file() and any(path.match(pattern) for pattern in file_patterns):
                try:
                    log.debug(f"Adding ignore file: {path}")
                    self.add_pattern_file(path)
                except Exception as e:
                    log.warning(f"Failed to add ignore file {path}: {e}")

    def add_pattern_file(self, path: Path | str):
        """
        Add an ignore file to the parser.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Ignore file {path} does not exist.")

        parser = get_parser_from_file(path)
        self.parsers.append(parser)

    def add_pattern(self, pattern: str):
        """
        Add a pattern to the parser.
        """
        if not isinstance(pattern, str):
            raise TypeError("Pattern must be a string.")

        if not pattern:
            raise ValueError("Pattern cannot be empty.")

        self.path_ignores.append(pattern)

    def add_patterns(self, patterns: Iterable[str]):
        """
        Add a pattern to the parser.
        """
        if isinstance(patterns, str):
            patterns = [patterns]

        for pattern in patterns:
            if isinstance(pattern, list):
                self.add_patterns(pattern)
                continue

            if not pattern:
                raise ValueError("Pattern cannot be empty.")

            self.path_ignores.append(pattern)

    def is_match(self, path: str | Path) -> bool:
        """
        Check if the given path is ignored by any of the parsers or patterns.
        """
        # Check parsers
        for parser in self.parsers:
            if parser.match(path):
                return True
        # Check patterns
        for pattern in self.path_ignores:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def __len__(self) -> int:
        """
        Get the number of parsers and patterns.
        """
        return len(self.parsers) + len(self.path_ignores)
