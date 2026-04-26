#!/usr/bin/env bash
# Generate the injected demo site output for offline viewing.
#
# Reads demo/site/ HTML files, applies the forge-overlay injection
# (ops.js + ops.css tags), and writes the result to demo/generated/.
# Non-HTML files are copied unchanged.
#
# Usage:
#   ./demo/scripts/generate-demo.sh
#
# After running, open demo/generated/index.html in a browser to inspect
# the injected output. CSS/JS assets are referenced via absolute paths
# (/ops/ops.css, /ops/ops.js) so they won't resolve from file:// - use
# the run-demo.sh server for full fidelity, or inspect the HTML source.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SITE_DIR="$DEMO_DIR/site"
OVERLAY_DIR="$DEMO_DIR/overlay"
OUT_DIR="$DEMO_DIR/generated"

# Clean previous output
rm -rf "$OUT_DIR"

echo "Generating injected demo site..."
echo "  source:  $SITE_DIR"
echo "  overlay: $OVERLAY_DIR"
echo "  output:  $OUT_DIR"
echo ""

# Use the Python injection pipeline directly
uv run python -c "
import shutil
from pathlib import Path
from forge_overlay.inject import SNIPPET

site = Path('$SITE_DIR')
out = Path('$OUT_DIR')

for src_file in site.rglob('*'):
    if src_file.is_dir():
        continue
    rel = src_file.relative_to(site)
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    if src_file.suffix == '.html':
        html = src_file.read_bytes()
        marker = b'</head>'
        idx = html.lower().find(marker)
        if idx != -1:
            html = html[:idx] + SNIPPET.encode() + html[idx:]
        dest.write_bytes(html)
        print(f'  injected: {rel}')
    else:
        shutil.copy2(src_file, dest)
        print(f'  copied:   {rel}')

# Also copy overlay assets into generated/ops/ for self-contained viewing
ops_dir = out / 'ops'
ops_dir.mkdir(parents=True, exist_ok=True)
overlay = Path('$OVERLAY_DIR')
for f in overlay.iterdir():
    if f.is_file():
        shutil.copy2(f, ops_dir / f.name)
        print(f'  overlay:  ops/{f.name}')

print()
print(f'Done. View: {out}/index.html')
"
