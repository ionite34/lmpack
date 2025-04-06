# lmpack 📦✨

**Effortlessly pack your project context for Large Language Models (LLMs) with intelligence and sensible defaults.**

[![PyPI version](https://badge.fury.io/py/lmpack.svg)](https://badge.fury.io/py/lmpack)

Tired of manually curating files for your LLM prompts? `lmpack` intelligently packs your project to a single markdown file, handling the noise so you don't have to. Just `pip install lmpack` and run!

**What makes `lmpack` different?**

*   🧠 **Git Aware:** Auto-detects `.gitignore` even when run from subdirectories. Labels files using git paths, or simple relative paths if not in a repo.
*   🤫 **Smart Defaults:** Ignores common clutter (`.git`, `node_modules`, etc.) and skips content of images/binaries out-of-the-box.
*   🤖 **LLM Ignore Files:** Automatically detects `.aiignore`, `.aiexclude`, `.cursorignore`, to skip content, but keeping them in the directory tree structure.
*   **📊 Granular Token Counting (Optional):** See exactly which parts of your project are token-heavy! Uses `tiktoken` (`cl100k_base` default) for accurate estimates. Provides both a detailed tree view and a total count.
*   **✨ Rich & Plain Tree Output:** Visualize your project structure using a beautiful Rich-powered tree in your terminal or a plain text version for files.
*   🛡️ **Safe Output:** Uses `.lmpack.md` to prevent self-inclusion issues.

**See it in action:** 👇

---

### Scenario 1: Running from a Subdirectory

No need to be in the root, `lmpack` finds your project's `.gitignore`.

**Project:**
```
my-repo/
├── .git/
├── .gitignore  <-- Contains "logs/" (Auto-detected)
├── src/
│   └── utils/
│       └── helpers.py  <-- You are here
├── logs/         <-- Will be ignored
```

**Command:**
```bash
# You are in my-repo/src/utils
lmpack
```

**Result:** `lmpack` detects `.git` and uses `../../.gitignore` automatically. `logs/` is correctly excluded. The file paths will be constructed relative to your repository root. ✅

---

### Scenario 2: Handling Noise & LLM-Specific Ignores

Defaults + LLM ignore files work together seamlessly.

**Project:**
```
another-project/
├── .git/            <-- Ignored by default
├── .gitignore
├── .aiexclude       <-- Contains "data/*.csv" (Auto-detected)
├── node_modules/    <-- Ignored by default
├── src/
│   └── data/
│       └── huge_dataset.csv <-- Ignored via .aiexclude
├── images/
│   └── logo.png      <-- Content skipped by default
└── package-lock.json <-- Content skipped by default
```

**Command:**
```bash
# You are in another-project/
lmpack
```

**Result:** `.git`, `node_modules`, the CSV file, and the content of the lockfile/image are all correctly handled without extra flags. ✅

---

### Scenario 3: Pinpointing Token Usage

Identify token hotspots easily.

**Command:**
```bash
cd my-project/
pip install lmpack[tiktoken]
lmpack --count-tokens
```

**Output (Terminal Tree):**
```
📂 my-project (15,820 tokens)
┣━━ 📂 app (12,105 tokens)  <-- High usage here!
┃   ┣━━ 🐍 main.py (5,300 tokens)
┃   ┗━━ ...
┣━━ 📂 tests (3,500 tokens)
┗━━ ...
```

**Result:** The token-annotated tree immediately highlights that the `app/` directory is the major token consumer. ✅

---

## Installation 🚀

If you want token counting capabilities (recommended), install with the `tiktoken` extra:

```bash
pip install lmpack[tiktoken]
```

## Quick Start ⚡

Navigate to a folder you want to send to your LLM and simply run:

```bash
lmpack
```

This will create a `yourproject_context.lmpack.md` file in the current directory, containing your project's source tree and relevant file contents.

To include token counting:

```bash
lmpack --count-tokens
```

This will print a token-annotated tree to your terminal and generate the context file.

## Usage & Options ⚙️

```bash
Usage: lmpack [OPTIONS] [INDEX_PATH]

  Generates a single text file containing the content of files within a
  directory or git repository, respecting ignore rules, formatting each file,
  and optionally counting tokens.

Arguments:
  [INDEX_PATH]  Path to folder to index. [default: .]

Options:
  -o, --output DIRECTORY          Directory for the main context file. [default: .]
  --output-name TEXT              Template for the main context file name. Use
                                  {repo_name}, {index_path}, {rel_index_path}
                                  placeholders. [default: {repo_name}_context.lmpack.md]
  --repo-root DIRECTORY           Path to the git root that contains the index
                                  path, detected if not provided.
  -i, --include TEXT              Include only files matching the given comma
                                  seperated pattern(s). Supports fnmatch globbing.
  -e, --exclude TEXT              Exclude files matching the given comma
                                  seperated pattern(s). Supports fnmatch globbing.
  -g, --gitignore TEXT            .gitignore/.aiexclude/.aiignore type files to
                                  use. Comma separated list of file paths.
  --count-tokens                  Enable token counting (requires tiktoken).
  --encoding TEXT                 Tiktoken encoding (e.g., cl100k_base). [default: cl100k_base]
  --tree-format [rich|plain|none] Format for the directory tree output. [default: rich]
  --tree-output FILE              Optional file path to write the plain text tree.
  -v, --verbose                   Enable verbose output.
  --help                          Show this message and exit.
```

**Key Options:**

*   `--include`, `--exclude`: Use standard glob patterns (like `.gitignore`) to fine-tune included/excluded files beyond the defaults.
*   `--count-tokens`: Enable token counting.
*   `--tree-format`: Choose how (or if) the directory tree is displayed (`rich` default for terminals, `plain`, `none`).
*   `--tree-output`: Save the plain text tree to a separate file.

## Ignoring Files

`lmpack` uses multiple layers for ignoring files:

1.  **Default Ignores:** Built-in patterns for common directories/files (see code for full list).
2.  **Detected `.gitignore` / `.dockerignore`:** Automatically found in the `INDEX_PATH` and the detected Git root.
3.  **User-Provided `--gitignore` Files:** Specify additional ignore files.
4.  **User-Provided `--exclude` Patterns:** Add specific command-line exclusion patterns.
5.  **Content Ignores:** Files whose content should be skipped (default list includes lockfiles, images, etc.). Can be extended by creating `.aiignore` or `.cursorignore` files (similar syntax to `.gitignore`).

## Contributing 🙏

Contributions are welcome and greatly appreciated! `lmpack` aims to be a community-driven tool, and your help can make it even better.

Whether it's reporting a bug, suggesting a feature, improving documentation, or submitting code, your input is valuable.

**Ways to Contribute:**

*   **🐛 Report Bugs:** If you find a bug, please open an issue on GitHub detailing the problem, your environment, and steps to reproduce it.
*   **💡 Suggest Features:** Have an idea for a new feature or improvement? Open an issue to discuss it first.
*   **📖 Improve Documentation:** Found a typo or think something could be clearer? Feel free to open an issue or submit a PR with improvements.
*   **💻 Submit Pull Requests:** For code contributions, please follow these general steps:
    1.  Fork the repository.
    2.  Create a new branch for your feature or bug fix (e.g., `feature/add-cool-thing` or `fix/resolve-that-bug`).
    3.  Make your changes. Try to follow the existing code style.
    4.  Add tests for any new functionality or bug fixes.
    5.  Ensure existing tests pass.
    6.  Open a Pull Request (PR) against the `main` branch, clearly describing your changes.

**Development Setup:**

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

1.  Clone the repository:
    ```bash
    git clone https://github.com/ionite34/lmpack.git
    cd lmpack
    ```
2.  Install dependencies (including development tools and extras like `tiktoken`):
    ```bash
    poetry install --all-extras
    ```

We aim for a positive and respectful contribution environment. Please adhere to standard open-source etiquette ❤️

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
