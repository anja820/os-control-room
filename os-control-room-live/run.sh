#!/usr/bin/env bash
# Launch the LIVE OS Control Room on your Linux VM.
#
#   ./run.sh
#
# Needs Python 3 and Linux /proc (any normal Linux VM). No pip installs.
# Optional but recommended for the scheduling demo: util-linux (taskset, renice)
#   sudo apt install -y util-linux procps

set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3 is required. Install with: sudo apt install -y python3"
  exit 1
fi

if [ ! -d /proc ]; then
  echo "This tool manages REAL Linux processes and needs /proc. Run it on Linux."
  exit 1
fi

exec "$PY" oscr.py "$@"
