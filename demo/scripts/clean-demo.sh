#!/usr/bin/env bash
# Clean generated/cached files from the demo directory.
#
# Removes:
#   - demo/generated/ (output of generate-demo.sh)
#   - __pycache__ dirs
#   - .pytest_cache dirs
#
# Does NOT remove the demo vault source, site, or overlay content.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$DEMO_DIR/.." && pwd)"

echo "Cleaning generated files..."

# Generated demo output
if [ -d "$DEMO_DIR/generated" ]; then
  rm -rf "$DEMO_DIR/generated"
  echo "  removed: demo/generated/"
fi

# Demo directory caches
find "$DEMO_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DEMO_DIR" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Repo-wide generated outputs
rm -rf "$REPO_DIR/.pytest_cache"
rm -rf "$REPO_DIR/.mypy_cache"
rm -rf "$REPO_DIR/.ruff_cache"
rm -f "$REPO_DIR/.coverage"
rm -rf "$REPO_DIR/htmlcov"

echo "Done."
