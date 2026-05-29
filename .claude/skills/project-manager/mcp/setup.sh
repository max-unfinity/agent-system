#!/usr/bin/env bash
# Reproducible setup for pmkit-render MCP server.
# Run once on a new machine. Assumes: Ubuntu/Debian, curl, git.
set -euo pipefail

VENV_DIR="${VENV_DIR:-$HOME/max-eliseev-venv}"
NODE_MAJOR=20

echo "==> Installing nvm"
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi
. "$NVM_DIR/nvm.sh"

echo "==> Installing Node.js $NODE_MAJOR via nvm"
nvm install "$NODE_MAJOR"
nvm alias default "$NODE_MAJOR"
echo "Node $(node --version), npm $(npm --version)"

echo "==> Installing mermaid-cli"
npm install -g @mermaid-js/mermaid-cli
echo "mmdc at $(which mmdc)"

echo "==> Installing Python dependencies into $VENV_DIR"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet "mcp[cli]" pyyaml jsonschema

echo "==> Appending nvm + venv env to ~/.bashrc (idempotent)"
MARKER="# pmkit-render env"
if ! grep -qF "$MARKER" "$HOME/.bashrc" 2>/dev/null; then
    cat >> "$HOME/.bashrc" <<'EOF'

# pmkit-render env
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
export VIRTUAL_ENV="$HOME/max-eliseev-venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
EOF
    echo "  Added to ~/.bashrc"
else
    echo "  ~/.bashrc already has $MARKER — skipped"
fi

echo "==> Done. Restart your shell or run: source ~/.bashrc"
