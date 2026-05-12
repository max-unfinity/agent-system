#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SERVICE_NAME="claude-remote"
TMUX_SESSION="claude"
CURRENT_USER="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$CURRENT_USER" | cut -d: -f6)"
# CLAUDE_CMD: override via env, else default to <user-home>/.local/bin/claude,
# else fall back to whatever is on the invoking user's PATH.
CLAUDE_CMD="${CLAUDE_CMD:-${USER_HOME}/.local/bin/claude}"
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[x]${NC} $*"; exit 1; }

# ── Must run as root ──────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Run with sudo: sudo bash $0"

# ── Install tmux if missing ───────────────────────────────────────────────────
if ! command -v tmux &>/dev/null; then
  info "tmux not found — installing..."
  apt-get update -qq && apt-get install -y tmux
  info "tmux installed: $(tmux -V)"
else
  info "tmux already installed: $(tmux -V)"
fi

# ── Resolve claude binary ─────────────────────────────────────────────────────
if [[ ! -x "$CLAUDE_CMD" ]]; then
  # Try the invoking user's PATH (loads their shell profile)
  RESOLVED="$(sudo -u "$CURRENT_USER" -i bash -c 'command -v claude' 2>/dev/null || true)"
  if [[ -n "$RESOLVED" && -x "$RESOLVED" ]]; then
    CLAUDE_CMD="$RESOLVED"
  else
    error "claude binary not found. Tried: $CLAUDE_CMD and ${CURRENT_USER}'s PATH. Set CLAUDE_CMD=/path/to/claude and re-run."
  fi
fi
info "Using claude binary: $CLAUDE_CMD"

# ── Write systemd service file ────────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
info "Writing service file: $SERVICE_FILE"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Claude Code Remote Control (tmux)
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=${CURRENT_USER}
Environment="HOME=/home/${CURRENT_USER}"
WorkingDirectory=${USER_HOME}
ExecStart=/usr/bin/tmux new-session -d -s ${TMUX_SESSION} "${CLAUDE_CMD} --verbose --remote-control $(hostname -s)"
ExecStartPost=/bin/sh -c 'sleep 3 && /usr/bin/tmux send-keys -t ${TMUX_SESSION} Enter'
ExecStop=/usr/bin/tmux kill-session -t ${TMUX_SESSION}
KillMode=none

[Install]
WantedBy=multi-user.target
EOF

# ── Enable and start ──────────────────────────────────────────────────────────
info "Reloading systemd..."
systemctl daemon-reload

info "Enabling service (auto-start on boot)..."
systemctl enable "$SERVICE_NAME"

# Stop first in case it was already running
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
sleep 1

info "Starting service..."
systemctl start "$SERVICE_NAME"
sleep 2

# ── Status check ──────────────────────────────────────────────────────────────
if systemctl is-active --quiet "$SERVICE_NAME"; then
  info "Service is running ✓"
else
  warn "Service may have failed. Check with:"
  echo "    journalctl -u ${SERVICE_NAME} -n 30"
  exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}All done!${NC} Useful commands:"
echo ""
echo "  Attach to Claude:       tmux attach -t ${TMUX_SESSION}"
echo "  Detach (keep running):  Ctrl+B, then D"
echo ""
echo "  Service status:         sudo systemctl status ${SERVICE_NAME}"
echo "  Live logs:              journalctl -u ${SERVICE_NAME} -f"
echo "  Restart:                sudo systemctl restart ${SERVICE_NAME}"
echo "  Stop:                   sudo systemctl stop ${SERVICE_NAME}"
echo "  Remove from boot:       sudo systemctl disable ${SERVICE_NAME}"