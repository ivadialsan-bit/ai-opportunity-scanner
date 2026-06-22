#!/usr/bin/env bash
set -e

cd /root/ai-opportunity-scanner
source .venv/bin/activate

TS=$(date +%Y%m%d_%H%M%S)
OUT_DIR="results/batch_${TS}"
mkdir -p "$OUT_DIR"

CITIES=(
  "Волгоград"
  "Краснодар"
  "Ростов-на-Дону"
  "Астрахань"
  "Саратов"
)

QUERY="кондиционеры"

echo "========== AI OPPORTUNITY SCANNER :: 5 CITIES =========="
echo "query=$QUERY"
echo "out_dir=$OUT_DIR"
echo

for CITY in "${CITIES[@]}"; do
  SAFE_CITY=$(echo "$CITY" | tr '[:upper:]' '[:lower:]' | sed 's/ /_/g; s/\//_/g')
  OUT_FILE="${OUT_DIR}/${SAFE_CITY}_${QUERY}.csv"

  echo
  echo "========== SCAN: $CITY =========="

  python -m scanner.cli \
    --city "$CITY" \
    --query "$QUERY" \
    --source osm \
    --limit 100 \
    --min-confidence medium \
    --output "$OUT_FILE" || true

  sleep 3
done

echo
echo "========== BATCH FILES =========="
ls -lah "$OUT_DIR"

echo
echo "========== ROW COUNTS =========="
for f in "$OUT_DIR"/*.csv; do
  if [ -f "$f" ]; then
    rows=$(($(wc -l < "$f") - 1))
    echo "$rows leads :: $f"
  fi
done

echo
echo "========== MERGE CSV =========="
MERGED="results/sales_leads_5_cities_${TS}.csv"
first=1

for f in "$OUT_DIR"/*.csv; do
  if [ -f "$f" ]; then
    if [ "$first" -eq 1 ]; then
      cat "$f" > "$MERGED"
      first=0
    else
      tail -n +2 "$f" >> "$MERGED"
    fi
  fi
done

echo "MERGED=$MERGED"
echo

echo "========== MERGED CHECK =========="
wc -l "$MERGED"
head -5 "$MERGED"
