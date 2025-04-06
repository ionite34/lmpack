import logging
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from lmpack.lm_packer import LmPacker

log = logging.getLogger(__name__)

app = typer.Typer()
console = Console()

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
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose output.")
    ] = False,
):
    """
    Generates a single text file containing the content of files within a git repository,
    respecting .gitignore rules and formatting each file with path and type information.
    """

    if verbose:
        log.setLevel(logging.DEBUG)

    log.debug(f"Index path: {index_path}")

    packer = LmPacker(index_path)

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

    # Detect ignore files in index and git root
    packer.file_ignores.scan_add_pattern_files(index_path, DEFAULT_IGNORES_FILES)
    if git_root:
        packer.file_ignores.scan_add_pattern_files(git_root, DEFAULT_IGNORES_FILES)

    # Detect content ignore files in index and git root
    packer.content_ignores.scan_add_pattern_files(index_path, DEFAULT_CONTENT_IGNORE_FILES)
    if git_root:
        packer.content_ignores.scan_add_pattern_files(git_root, DEFAULT_CONTENT_IGNORE_FILES)

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

    output_file = Path(output_path).joinpath(output_name)

    log.debug(f"Output file path: {output_file}")

    # Start parsing
    with open(output_file, "w", encoding="utf-8") as outfile:
        # 1. Write tree
        tree_output = "# Source Tree\n\n```\n"
        tree_output += packer.create_ascii_tree()
        tree_output += "\n```\n\n# File Contents\n\n"

        outfile.write(tree_output)

        # 2. Write file contents
        for content in packer.iter_file_contents():
            outfile.write(content)

    typer.echo(typer.style(f"Context written to {output_file}", fg=typer.colors.GREEN))

    for ignore_type, count in packer.COUNT_IGNORES.items():
        typer.echo(
            typer.style(
                f"Ignored {count} files based on {ignore_type} rules.", fg=typer.colors.YELLOW
            )
        )

    typer.echo(
        typer.style(
            f"Included {packer.COUNT_FILES['included_no_content']} files without content.",
            fg=typer.colors.YELLOW,
        )
    )

    typer.echo(
        typer.style(
            f"Total files included: {packer.COUNT_FILES['included']}/{packer.COUNT_FILES['processed']}",
            fg=typer.colors.GREEN,
        )
    )


if __name__ == "__main__":
    app()
