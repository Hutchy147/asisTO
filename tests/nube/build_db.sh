#!/usr/bin/env bash
# tests/nube/build_db.sh <base>
#
# Arma una base DESCARTABLE para las pruebas que corren en la nube (Python,
# sin PowerShell): schema.sql + seed.sql + hashes bcrypt. Nunca toca `asisto`.
# Neutraliza el DROP/CREATE/USE de las primeras lineas del schema sobre una
# copia, igual que hace tests/db/setup/build_test_db.ps1.
#
# Uso:  tests/nube/build_db.sh asisto_test_nube [seed.sql|seed_demo.sql]
set -euo pipefail
BASE="${1:?Falta el nombre de la base}"
SEED="${2:-seed.sql}"
if [ "$BASE" = "asisto" ]; then
  echo "Esta base es la real: no se arma ni se borra desde aca." >&2
  exit 1
fi
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp)"
python3 - "$RAIZ/backend/database/schema.sql" "$TMP" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
cabecera = ("DROP DATABASE IF EXISTS asisto;\nCREATE DATABASE asisto\n"
            "  CHARACTER SET utf8mb4\n  COLLATE utf8mb4_unicode_ci;\nUSE asisto;\n")
if cabecera not in s:
    sys.exit("La cabecera del schema cambio: no se puede neutralizar")
open(dst, 'w', encoding='utf-8').write(s.replace(cabecera, '', 1))
PY
mysql -e "DROP DATABASE IF EXISTS \`$BASE\`; CREATE DATABASE \`$BASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql "$BASE" < "$TMP" > /dev/null
mysql "$BASE" < "$RAIZ/backend/database/$SEED" > /dev/null
mysql -e "GRANT ALL ON \`$BASE\`.* TO 'asisto_app'@'localhost'; FLUSH PRIVILEGES;"
rm -f "$TMP"
( cd "$RAIZ/backend" && DB_NAME="$BASE" /home/claude/venv/bin/python scripts/generar_hashes.py --aplicar --todos | tail -1 )
echo "Base $BASE lista ($SEED)"
