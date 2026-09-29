#!/usr/bin/env bash
# Instalează skill-ul jurist pentru Claude Code:
#   1. verifică Python >= 3.10, PyYAML și SQLite cu FTS5;
#   2. copiază codul în copia globală (implicit ~/.claude/skills/jurist, sau $JURIST_GLOBAL_SKILL);
#   3. copiază baza de date data/legal.db (sync_skill.py nu copiază data/);
#   4. scrie launcher-ul `jurist` în ~/.local/bin (sau $JURIST_BIN_DIR).
# Rulează din rădăcina repository-ului: ./scripts/install_skill.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${JURIST_GLOBAL_SKILL:-$HOME/.claude/skills/jurist}"
BIN_DIR="${JURIST_BIN_DIR:-$HOME/.local/bin}"

python3 - <<'PY'
import sqlite3, sys
if sys.version_info < (3, 10):
    sys.exit(f"jurist: e nevoie de Python >= 3.10 (găsit {sys.version.split()[0]})")
try:
    import yaml  # noqa: F401
except ImportError:
    sys.exit("jurist: lipsește PyYAML -> python3 -m pip install --user 'PyYAML>=6.0'")
conn = sqlite3.connect(":memory:")
try:
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='unicode61 remove_diacritics 2')")
except sqlite3.OperationalError as exc:
    sys.exit(f"jurist: SQLite {sqlite3.sqlite_version} fără FTS5/remove_diacritics 2 (e nevoie de >= 3.27): {exc}")
PY

if [ ! -s "$REPO/data/legal.db" ]; then
    echo "jurist: lipsește data/legal.db; rulează întâi scripts/fetch_corpus.py și scripts/ingest_corpus.py --fresh" >&2
    exit 1
fi

JURIST_GLOBAL_SKILL="$DEST" python3 "$REPO/scripts/sync_skill.py"
mkdir -p "$DEST/data"
cp "$REPO/data/legal.db" "$REPO/data/manifest.json" "$REPO/data/schema_version.txt" "$DEST/data/"

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/jurist" <<EOF
#!/usr/bin/env bash
# jurist skill launcher — global install at $DEST
export PYTHONPATH="$DEST\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m jurist "\$@"
EOF
chmod +x "$BIN_DIR/jurist"

echo "jurist instalat în $DEST; launcher: $BIN_DIR/jurist"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Atenție: $BIN_DIR nu e în PATH — adaugă-l în ~/.bashrc / ~/.zshrc." ;;
esac
JURIST_SESSION=install "$BIN_DIR/jurist" corpus-status --json | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print('verificare:', d['ok'], d['counts'])"
