import enum
import logging
import subprocess
from pathlib import Path
from typing import Annotated

import rich.styled
import typer
from rich.console import Console
from rich.table import Table
from rich import box
from rich import color

from lmpack.lm_packer import LmPacker
from lmpack.tokenizers import get_tokenizer, NullTokenizerBackend

log = logging.getLogger(__name__)

app = typer.Typer()
console = Console(markup=True)
err_console = Console(stderr=True, markup=True)

# Define default ignores
DEFAULT_IGNORES = [
    ".git/*",
    ".vs/*",
    ".vscode/*",
    ".idea/*",
    "__pycache__/*",
    "node_modules/*",
    "*/obj/*",
    "*/bin/*",
    "*.lmpack.md",
    "*.lmpack.txt",
]

DEFAULT_IGNORES_FILES = [
    ".gitignore",
    ".dockerignore",
]

# Files to include only file name
DEFAULT_CONTENT_IGNORES = [
    ".gitignore",
    ".dockerignore",
    ".gitattributes",
    ".editorconfig",
    "poetry.lock",
    "package-lock.json",
    "*.g.cs",
    "*.svg",
    "*.png",
    "*.jpg",
]

DEFAULT_CONTENT_IGNORE_FILES = [
    ".aiexclude",
    ".aiignore",
    ".cursorignore",
]

DEFAULT_OUTPUT_NAME_FIXED = "context.lmpack.md"
DEFAULT_OUTPUT_NAME_TEMPLATE = "{repo_name}_context.lmpack.md"


def try_find_git_root(path: Path) -> Path | None:
    """
    Find the root directory of a git repository the given path is inside, if any.
    """
    try:
        # Check if the path is a directory within a git repository
        result = subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=path, stderr=subprocess.PIPE
        )
        if result.decode("utf-8").strip() == "true":
            # If the path is inside a git repository, find the root directory
            git_root = (
                subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], cwd=path, stderr=subprocess.PIPE
                )
                .decode("utf-8")
                .strip()
            )
            log.debug(f"Git root found: {git_root}")
            return Path(git_root)
    except subprocess.CalledProcessError:
        log.debug(f"Not a valid git repository: {path}")

    return None


def comma_list(raw: str) -> list[str]:
    return raw.split(",")


class TreeFormat(str, enum.Enum):
    RICH = "rich"
    PLAIN = "plain"
    NONE = "none"


@app.command()
def create_repo_context(
        index_path: Path = typer.Argument(
            ".",
            help="Path to folder to index for packing.",
            dir_okay=True,
            file_okay=False,
            exists=True,
            resolve_path=True,
        ),
        output_path: Path = typer.Option(
            ".",
            "--output",
            help="Path to directory to write the output file to.",
            dir_okay=True,
            file_okay=False,
            exists=True,
            resolve_path=True,
        ),
        output_name_template: str = typer.Option(
            DEFAULT_OUTPUT_NAME_TEMPLATE,
            "--output-name",
            help="Template for the output file name. Use {repo_name}, {index_path}, {rel_index_path} placeholders.",
        ),
        repo_root: Path | None = typer.Option(
            None,
            "--repo-root",
            help="Path to the git root that contains the index path, detected if not provided.",
            dir_okay=True,
            file_okay=False,
            exists=True,
            resolve_path=True,
        ),
        include_patterns: Annotated[
            list[str] | None,
            typer.Option(
                "--include",
                "-i",
                parser=comma_list,
                help="Include only patterns matching the given comma seperated pattern(s).",
            ),
        ] = None,
        include_files: Annotated[
            list[str] | None,
            typer.Option(
                "--include-file",
                parser=comma_list,
                help="Include only files matching the given comma seperated pattern(s).",
            ),
        ] = None,
        ignore_patterns: Annotated[
            list[str] | None,
            typer.Option(
                "--exclude",
                "-e",
                parser=comma_list,
                help="Exclude files matching the given comma seperated pattern(s).",
            ),
        ] = None,
        ignore_files: Annotated[
            list[str] | None,
            typer.Option(
                "--gitignore",
                "-g",
                parser=comma_list,
                help=".gitignore/.aiexclude/.aiignore type files to use. Comma separated list of file paths.",
            ),
        ] = None,
        count_tokens: Annotated[
            bool, typer.Option("--count-tokens", "-t", help="Enable token counting using tiktoken.")
        ] = False,
        tokenizer_encoding: Annotated[
            str,
            typer.Option("--encoding", help="Tiktoken encoding to use (e.g., cl100k_base, p50k_base)."),
        ] = "cl100k_base",
        tree_format: Annotated[
            TreeFormat,
            typer.Option("--tree-format", case_sensitive=False, help="Format for the directory tree output.")
        ] = TreeFormat.RICH,
        tree_output_file: Annotated[
            Path | None,
            typer.Option(
                "--tree-output",
                help="Optional file path to write the token-annotated tree.",
                dir_okay=False,
                file_okay=True,
                writable=True,
                resolve_path=True,
            ),
        ] = None,
        print_tree: Annotated[
            bool,
            typer.Option(
                "--print-tree",
                help="Print the token-annotated tree to stderr (default if counting tokens and not writing to file).",
            ),
        ] = False,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Enable verbose output.")
        ] = False,
):
    """
    Generates a single text file containing the content of files within a git repository,
    respecting .gitignore rules and formatting each file with path and type information.
    """

    if verbose:
        logging.getLogger("lmpack").setLevel(logging.DEBUG)
    else:
        logging.getLogger("lmpack").setLevel(logging.INFO)

    log.debug(f"Index path: {index_path}")

    # --- Tokenizer Setup ---
    tokenizer = get_tokenizer(tokenizer_encoding, count_tokens)
    log.debug(f"Using tokenizer: {tokenizer.__class__.__name__} ({tokenizer.encoding_name})")

    packer = LmPacker(index_path, tokenizer=tokenizer)

    # Setup default ignores
    packer.file_ignores.add_patterns(DEFAULT_IGNORES)

    # User provided ignore patterns
    if ignore_patterns:
        log.debug(f"Adding provided ignore patterns: {ignore_patterns}")
        packer.file_ignores.add_patterns(ignore_patterns)

    packer.content_ignores.add_patterns(DEFAULT_CONTENT_IGNORES)

    # Find git root for .gitignores
    git_root = try_find_git_root(index_path)
    git_name = git_root.name if git_root else index_path.name

    # Add ignore files explicitly provided by user first
    if ignore_files:
        for file_path_str in ignore_files:
            file_path = Path(file_path_str)
            if file_path.exists():
                log.debug(f"Adding user-specified ignore file: {file_path}")
                packer.file_ignores.add_pattern_file(file_path)
            else:
                log.warning(f"User-specified ignore file not found: {file_path}")

    # Detect ignore files in index and git root
    packer.file_ignores.scan_add_pattern_files(index_path, DEFAULT_IGNORES_FILES)
    if git_root:
        packer.file_ignores.scan_add_pattern_files(git_root, DEFAULT_IGNORES_FILES)

    # Detect content ignore files in index and git root
    packer.content_ignores.scan_add_pattern_files(index_path, DEFAULT_CONTENT_IGNORE_FILES)
    if git_root:
        packer.content_ignores.scan_add_pattern_files(git_root, DEFAULT_CONTENT_IGNORE_FILES)

    # User provided include patterns
    if include_patterns:
        include_patterns = include_patterns[0]  # apparently a list of lists
        log.debug(f"Adding include patterns: {include_patterns}")
        packer.include_matcher.add_patterns(include_patterns)
    if include_files:
        include_files = include_files[0]  # apparently a list of lists
        log.debug(f"Adding include files: {include_files}")
        # Add '**/filename' to include only the file name
        packer.include_matcher.add_patterns([f"**/{pattern}" for pattern in include_files])

    # Name output
    if output_name_template:
        log.debug(f"Output name template: {output_name_template}")
        output_name = output_name_template.format(
            repo_name=git_name,
            index_path=index_path.name,
            rel_index_path=index_path.relative_to(git_root) if git_root else index_path,
        )
    else:
        output_name = DEFAULT_OUTPUT_NAME_FIXED

    # Get output location
    if not output_path:
        output_path = index_path

    output_path.mkdir(parents=True, exist_ok=True)
    main_output_file = output_path.resolve().joinpath(output_name)
    log.debug(f"Output file path: {main_output_file}")

    # --- Build Tree ---
    console.print(f"Building file tree for [cyan]{index_path}[/]...")
    root_node = packer.build_tree()
    total_tokens = root_node.get_total_tokens() if count_tokens else 0
    console.print("Tree build complete.")

    # --- Determine effective tree format ---
    effective_tree_format = tree_format
    # If not counting tokens, tree format doesn't make sense unless explicitly plain
    if not count_tokens and effective_tree_format == TreeFormat.RICH:
        effective_tree_format = TreeFormat.PLAIN  # Fallback to plain if not counting tokens
    # If outputting to a file, always use plain format for the file content
    is_writing_tree_to_file = tree_output_file is not None
    # If printing to console, decide between rich/plain based on terminal capability
    is_printing_to_console = not is_writing_tree_to_file and effective_tree_format != TreeFormat.NONE
    can_use_rich = err_console.is_terminal  # Check if stderr is a terminal

    if is_printing_to_console and not can_use_rich and effective_tree_format == TreeFormat.RICH:
        log.debug("Output is not a TTY, falling back to plain tree format for console.")
        effective_tree_format = TreeFormat.PLAIN  # Fallback for non-TTY

    # --- Handle Tree Output ---
    if effective_tree_format != TreeFormat.NONE:
        tree_content_plain = None  # For file output or plain console
        tree_content_rich = None  # For rich console output
        should_show_tokens_in_tree = count_tokens # Determine if tokens should be shown based on CLI flag

        log.debug(
            f"Generating tree output (Format: {effective_tree_format}, To file: {is_writing_tree_to_file}, To console: {is_printing_to_console})")

        # Generate necessary formats
        if is_writing_tree_to_file or effective_tree_format == TreeFormat.PLAIN:
            log.debug("Generating plain text tree...")
            tree_content_plain = packer.create_ascii_tree(root_node, show_tokens=should_show_tokens_in_tree)

        if is_printing_to_console and effective_tree_format == TreeFormat.RICH:
            log.debug("Generating Rich tree object...")
            tree_content_rich = packer.create_rich_tree(root_node, show_tokens=should_show_tokens_in_tree)

        # Write to file if requested (always plain)
        if is_writing_tree_to_file:
            if tree_content_plain is not None:
                console.print(f"Writing plain text tree to [yellow]{tree_output_file}[/]")
                try:
                    tree_output_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(tree_output_file, "w", encoding="utf-8") as f_tree:
                        f_tree.write(f"# Directory Tree for: {index_path}\n")
                        if count_tokens:
                            f_tree.write(f"# Encoding: {tokenizer.encoding_name}\n")
                        f_tree.write("\n")
                        f_tree.write(tree_content_plain)
                except Exception as e:
                    err_console.print(f"[bold red]Error writing tree file {tree_output_file}: {e}[/]")
            else:
                log.warning("Tree output file specified, but plain tree content wasn't generated.")

        # Print to console if needed
        elif is_printing_to_console:
            err_console.print("\n--- Directory Tree ---", )  # Header for console tree
            if effective_tree_format == TreeFormat.RICH and tree_content_rich:
                err_console.print(tree_content_rich)
            elif effective_tree_format == TreeFormat.PLAIN and tree_content_plain:
                err_console.print(tree_content_plain)
            err_console.print("--- End Tree ---\n", )

    # --- Write Main Output File ---
    console.print(f"Writing main context to [cyan]{main_output_file}[/]...")
    try:
        with open(main_output_file, "w", encoding="utf-8") as outfile:
            # 1. Write the clean source tree (regenerate without tokens)
            log.debug("Generating clean tree for main output file...")
            # --- Call the same packer instance, but disable tokens ---
            clean_tree_string = packer.create_ascii_tree(root_node, show_tokens=False)

            outfile.write("# Source Tree\n\n```\n")
            outfile.write(clean_tree_string)
            outfile.write("\n```\n\n# File Contents\n\n")

            # 2. Write file content blocks (using the original packer with token info if needed)
            block_count = 0
            for content_block in packer.iter_formatted_output_blocks(root_node):
                outfile.write(content_block)
                outfile.write("\n")
                block_count += 1
            log.debug(f"Wrote {block_count} file content blocks.")

        console.print(f"Context written to {main_output_file}", style="bold green")

    except Exception as e:
        console.print(f"[bold red]Error writing main output file {main_output_file}: {e}[/]")
        raise typer.Exit(code=1)

    # --- Display Stats ---
    stats = packer.stats
    table = Table(title="Processing Summary", show_header=False, box=box.ROUNDED)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Directories Processed:", str(stats["dirs_processed"]))
    table.add_row("Directories Ignored:", str(stats["dirs_ignored"]))
    table.add_row("Files Processed:", str(stats["files_processed"]))
    table.add_row("Files Ignored (File Pattern):", str(stats["files_ignored_file_pattern"]))
    table.add_row("Files Ignored (Include Pattern):", str(stats["files_ignored_include_pattern"]))
    table.add_row("Files Included (Content Skipped):", str(stats["files_content_skipped"]))
    table.add_row("Files Included (Binary):", str(stats["files_binary"]))
    table.add_row("Files Included (Read Error):", str(stats["files_read_error"]))
    table.add_row("Files Included (with Content):", str(stats["files_included_with_content"]))
    if count_tokens:
        table.add_row("Total Tokens Estimated:", f"{total_tokens:,}")  # Formatted number

    console.print(table)


if __name__ == "__main__":
    app()
