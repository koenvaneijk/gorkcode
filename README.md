# Gorkcode

<img src="logo.png" alt="Gorkcode" width="200"/>

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

Terminal-based AI coding assistant powered by xAI's Grok.

Edit your codebase using structured tool calls. Safe, minimal, and runs entirely in your terminal.

## Demo (`/roast` command)

Watch the [`/roast` demo](https://github.com/koenvaneijk/gorkcode/blob/main/.github/gorkcode_roast.mov) (video).

## ✨ Features

- **Precise Edits**: Exact find/replace on files with safety checks and linting.
- **Shell Commands**: Run commands (git, python, etc.) with explicit user approval.
- **Dynamic Context**: Load/drop specific files as needed, with repo map.
- **Built-in Commands**: `/roast`, `/add`, `!shell`, etc.
- **Git Integration**: Automatic commit tool.
- **Single-File**: Portable, zero dependencies beyond Python stdlib.

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

- Enter your request then **Ctrl+D** (EOF) to submit
- `/roast` - Roast this repository (see demo)
- `/add <glob>` - Add files matching glob to context
- `/drop <file>` - Remove a file from context
- `/clear` - Clear conversation history
- `/undo` - Undo last commit (`git reset --soft HEAD~1`)
- `!<cmd>` - Run a shell command and optionally add output to context
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