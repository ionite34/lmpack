from pathlib import Path

from lmpack.ignores import FilePatternMatcher


def create_ascii_tree(
    path: Path,
    ignore_matcher: FilePatternMatcher,
    base_path: Path = None,
    prefix: str = "",
    is_last: bool = True,
    max_depth: int = None,
    current_depth: int = 0,
) -> str:
    """
    Create an ASCII representation of the directory tree.

    Args:
        path: The path to create a tree for
        ignore_matcher: The ignore matcher to use
        base_path: The base path for relative path calculations
        prefix: The prefix for the current line
        is_last: Whether this item is the last in its parent directory
        max_depth: Maximum depth to traverse (None for unlimited)
        current_depth: Current depth in the traversal
    """
    if max_depth is not None and current_depth > max_depth:
        return ""

    # Initialize base_path if not provided
    if base_path is None:
        base_path = path

    # For the root directory, show its name without prefix
    if current_depth == 0:
        result = [path.name]
    else:
        result = [f"{prefix}{'└── ' if is_last else '├── '}{path.name}"]

    # Prepare prefix for children
    new_prefix = prefix + ("    " if is_last else "│   ")

    # If it's a directory, process its children
    if path.is_dir():
        # Get all items in the directory
        try:
            items = list(path.iterdir())

            # Filter out ignored items
            filtered_items = []
            for item in items:
                try:
                    rel_path = item.relative_to(base_path)
                    if not ignore_matcher.is_match(rel_path):
                        filtered_items.append(item)
                except ValueError:
                    # Skip items that can't be made relative to base_path
                    continue

            # Sort directories first, then files
            filtered_items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            # Process each item
            for i, item in enumerate(filtered_items):
                is_last_item = i == len(filtered_items) - 1
                child_tree = create_ascii_tree(
                    item,
                    ignore_matcher,
                    base_path,
                    new_prefix,
                    is_last_item,
                    max_depth,
                    current_depth + 1,
                )
                if child_tree:
                    result.append(child_tree)
        except PermissionError:
            # Handle permission errors gracefully
            result.append(f"{new_prefix}[Permission denied]")

    return "\n".join(result)
