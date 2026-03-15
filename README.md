# Gorkcode

<img src="logo.png" alt="Gorkcode" width="200"/>

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

Terminal-based AI coding assistant powered by xAI's Grok.

Edit your codebase using structured tool calls. Safe, minimal, and runs entirely in your terminal.

## Demo (`/roast` command)

Watch the [`/roast` demo](https://github.com/koenvaneijk/gorkcode/blob/main/.github/gorkcode_roast.mov) (video).

## ✨ Features

- **Structured Tools**: Uses `request_files`, `edit_file`, `create_file`, `run_shell_command`, `commit_changes` via function calls.
- **Precise Edits**: Exact string match find/replace with safety checks, Python linting, and diff preview.
- **Safe Shell**: Run commands only with explicit user approval; output can be added to context.
- **Dynamic Context**: Repo map always shown; explicitly load/drop files with `request_files`/`drop_files`.
- **Built-in Commands**: `/roast`, `/add`, `/status`, `/clear`, `/undo`, `!shell`, etc.
- **Git Integration**: Automatic `commit_changes` tool; `/undo` support.
- **Single-File**: Portable, zero dependencies beyond Python stdlib + xAI API key.

## 🛡️ AI Guidelines

The coding expert follows these strict rules (embedded in `gorkcode.py`):

- Think step by step before deciding to use tools
- Answer normally when no tool is needed
- Always read relevant files using `request_files` before editing them (unless creating a brand new file)
- Prefer small, precise edits. Make the 'find' string as short and unique as possible
- Preserve original formatting, whitespace, and surrounding code style exactly
- If an edit's exact find text is not found, read the file again and use a more precise match
- Only run shell commands when genuinely necessary
- After changes, call `commit_changes` with a short message if and only if files were actually modified
- Keep all user-facing answers concise

## 🚀 Quick Start

1. **API Key**: Get one from [console.x.ai](https://console.x.ai) (Grok API).

   ```bash
   export XAI_API_KEY=your-api-key-here
   ```
   
   To make this permanent, add it to your `~/.bashrc`:
   ```bash
   echo 'export XAI_API_KEY=your-api-key-here' >> ~/.bashrc
   source ~/.bashrc
   ```

2. **Download**:
   ```bash
   curl -O https://raw.githubusercontent.com/koenvaneijk/gorkcode/main/gorkcode.py
   chmod +x gorkcode.py
   ```

3. **Run** (in a project dir):
   ```bash
   ./gorkcode.py
   ```

4. **(Optional) Create an alias** for easy access from anywhere:

   Add this line to your `~/.bashrc` (or `~/.zshrc` for Zsh):
   ```bash
   alias gorkcode='/path/to/gorkcode.py'
   ```
   
   Then reload your shell:
   ```bash
   source ~/.bashrc
   ```
   
   Now you can simply run `gorkcode` from any directory.

## ⌨️ Commands

While running the REPL:

- Multi-line input; press **Ctrl+D** (EOF) to submit
- `/roast` - Roast this repository (see demo)
- `/add <glob>` - Add files matching glob pattern to context
- `/drop <file>` - Remove file from context
- `/status` - Show repo, context, model and usage info
- `/clear` - Clear conversation history and cost
- `/undo` - Undo last commit (`git reset --soft HEAD~1`)
- `!<cmd>` - Run shell command (optionally add output to context)
- `/help` - Show available commands
- `/exit` - Exit the program

## 🛠️ Development

```bash
git clone https://github.com/koenvaneijk/gorkcode.git
cd gorkcode
python3 gorkcode.py
```

The full system prompt and behavior rules for the AI are embedded directly in `gorkcode.py`.

## 📄 License

[AGPLV3](LICENSE) © [Koen van Eijk](https://github.com/koenvaneijk)