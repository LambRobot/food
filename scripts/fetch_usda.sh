#!/usr/bin/env bash
# Download the USDA FoodData Central bulk CSVs needed to (re)build the nutrition
# reference. Writes to data/usda_src/ (git-ignored — large & reconstructible).
# After running this, build the committed reference with:
#     python3 scripts/build_nutrition_reference.py
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/data/usda_src"
mkdir -p "$DIR"; cd "$DIR"

SR="FoodData_Central_sr_legacy_food_csv_2018-04.zip"
FF="FoodData_Central_foundation_food_csv_2025-12-18.zip"
BASE="https://fdc.nal.usda.gov/fdc-datasets"

for z in "$SR" "$FF"; do
  echo "Downloading $z ..."
  curl -fSL -o "$z" "$BASE/$z"
  unzip -o -q "$z"
done
echo "Done. USDA CSVs are in $DIR"
