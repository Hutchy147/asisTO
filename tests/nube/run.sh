#!/usr/bin/env bash
# tests/nube/run.sh [modulo ...]
# Reconstruye la base descartable y corre las pruebas de la nube. Cada corrida
# parte de una base limpia: las pruebas escriben y no se limpian.
set -euo pipefail
cd "$(dirname "$0")"
BASE="${ASISTO_BASE_NUBE:-asisto_test_nube}"
./build_db.sh "$BASE" > /dev/null
if [ "$#" -eq 0 ]; then set -- $(ls test_*.py | sed 's/\.py$//'); fi
DB_NAME="$BASE" PYTHONPATH=. /home/claude/venv/bin/python -W ignore -m unittest "$@" 2>&1 | grep -v " INFO \| WARNING " | tail -40
