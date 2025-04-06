from pathlib import Path


# Extension -> Markdown codeblock mapping
def get_codeblock_language(file_extension: str, default: str = "") -> str:
    """
    Returns the code block language for a given file extension.
    """
    ext_to_codeblock = {
        "py": "python",
        "js": "javascript",
        "html": "html",
        "css": "css",
        "json": "json",
        "cs": "csharp",
        "xml": "xml",
        "xaml": "xml",
        "axaml": "xml",
        "txt": "text",
        "md": "markdown",
        "gitignore": "text",
        "toml": "toml",
        "yml": "yaml",
        "yaml": "yaml",
        "config": "text",
        "csproj": "xml",
        "sln": "text",
        "sh": "bash",
        "bat": "batch",
        "cpp": "cpp",
        "c": "c",
        "java": "java",
        "go": "go",
        "php": "php",
        "rb": "ruby"
    }

    # Normalize the file extension
    file_extension = file_extension.lstrip('.').lower()

    return ext_to_codeblock.get(file_extension, default)


def to_disp_path(path: Path) -> str:
    """
    Convert a path to a display-friendly format.
    """
    return str(path).replace("\\", "/")
