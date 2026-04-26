#!/usr/bin/env bash
# Run the forge-overlay server against the demo vault content.
#
# Usage:
#   ./demo/scripts/run-demo.sh [--port PORT]
#
# Requires: devenv shell or activated venv with forge-overlay installed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SITE_DIR="$DEMO_DIR/site"
OVERLAY_DIR="$DEMO_DIR/overlay"
PORT="${1:-8080}"

if [[ "${1:-}" == "--port" ]]; then
  PORT="${2:-8080}"
fi

echo "=== forge-overlay demo ==="
echo "  site:    $SITE_DIR"
echo "  overlay: $OVERLAY_DIR"
echo "  port:    $PORT"
echo ""
echo "  http://127.0.0.1:$PORT/"
echo "  http://127.0.0.1:$PORT/notes/day-1"
echo "  http://127.0.0.1:$PORT/projects/forge"
echo ""
echo "  POST http://127.0.0.1:$PORT/internal/rebuild to simulate a rebuild."
echo "  GET  http://127.0.0.1:$PORT/ops/events for SSE stream."
echo ""

exec uv run forge-overlay \
  --site-dir "$SITE_DIR" \
  --overlay-dir "$OVERLAY_DIR" \
  --port "$PORT"
