#!/usr/bin/env bash
# setup_macos_py311.sh
# macOS setup script for hmrc-tax-mcp development environment.
# Installs Homebrew (if missing prompt), pyenv via Homebrew, Python 3.11.6,
# creates a virtualenv (.venv311) in the repo, installs server extras and
# starts the MCP stdio dev server.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY_VERSION="3.11.6"
VENV_DIR=".venv311"

echo "Repository root: $REPO_ROOT"
cd "$REPO_ROOT"

command_exists() { command -v "$1" >/dev/null 2>&1; }

# 1) Homebrew
if command_exists brew; then
  echo "Homebrew found"
else
  echo "Homebrew not found. Please install Homebrew first:"
  echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  echo "Then re-run this script. Exiting."
  exit 1
fi

# 2) Install build dependencies via brew
echo "Installing pyenv and build deps via Homebrew..."
brew update
brew install pyenv openssl readline xz zlib || true

# 3) Install pyenv (brew should have installed it)
if ! command_exists pyenv; then
  echo "pyenv not found after brew install; aborting"
  exit 1
fi

# Ensure pyenv is available in this script's environment
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
# Initialize pyenv for this shell (do not modify shell rc automatically)
if pyenv init --no-rehash >/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi

# 4) Install Python
if pyenv versions --bare | grep -qx "$PY_VERSION"; then
  echo "Python $PY_VERSION already installed via pyenv"
else
  echo "Installing Python $PY_VERSION (this may take several minutes)..."
  pyenv install "$PY_VERSION"
fi

# Use the repo-local pyenv version
pyenv local "$PY_VERSION"

# Determine the pyenv python binary (fallback to system python3)
PY_BIN="$(pyenv which python 2>/dev/null || true)"
if [ -z "$PY_BIN" ]; then
  PY_BIN="$(command -v python3 || true)"
fi
if [ -z "$PY_BIN" ]; then
  echo "No suitable python binary found (pyenv or system python3). Aborting."
  exit 1
fi

# 5) Create and activate virtualenv/venv using the pyenv python
if [ -d "$VENV_DIR" ]; then
  echo "Virtualenv $VENV_DIR already exists"
else
  echo "Creating venv $VENV_DIR using $($PY_BIN -V)"
  "$PY_BIN" -m venv "$VENV_DIR"
fi

# Activate venv for the remainder of the script
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Ensure pip comes from the venv python
python -m pip install --upgrade pip

# 6) Install project with server extras (mcp, click, etc.)
echo "Installing project (server extras)..."
python -m pip install -e '.[server]'

# If system python3 is not available, the pyenv-installed python will be used
# after 'pyenv local' above. Use 'python3' explicitly when creating the venv
# to avoid "python: command not found" on macOS.

# 7) (Optional) install uvicorn/fastapi for HTTP dev server
pip install 'uvicorn[standard]' fastapi || true

# 8) Final notes and shell rc guidance
cat <<EOF
Setup complete. Next steps (recommended):

1) Add pyenv init to your shell configuration (if not already present):

   # Add to ~/.zshrc or ~/.bashrc
   export PYENV_ROOT="$HOME/.pyenv"
   export PATH="$PYENV_ROOT/bin:$PATH"
   eval "$(pyenv init -)"

2) Activate the venv and run the MCP stdio server:

   cd "$REPO_ROOT"
   source $VENV_DIR/bin/activate
   python3 -m hmrc_tax_mcp.server

   Note: the MCP stdio server expects an MCP-compatible client (stdio transport).

3) Alternatively, run the HTTP dev server (convenient for manual testing):

   source $VENV_DIR/bin/activate
   python3 -m uvicorn src.hmrc_tax_mcp.server:app --reload --port 8000

EOF

# 9) Optionally start the MCP server now (commented out by default)
if [ "${START_NOW:-no}" = "yes" ]; then
  echo "Starting MCP stdio server in background..."
  # Start in background; user can inspect logs if desired
  nohup python3 -m hmrc_tax_mcp.server > hmrc-server.log 2>&1 &
  echo "Server started; logs: $REPO_ROOT/hmrc-server.log"
fi

exit 0
