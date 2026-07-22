#!/usr/bin/env bash
# Regenerate the whole data pipeline from committed inputs (source/ + usda_reference.json).
# Does NOT re-download USDA (that's scripts/fetch_usda.sh + build_nutrition_reference.py,
# which need the large raw dump). Run this after changing any script, then commit data/.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/parse_recipes.py
python3 scripts/score_recipes.py
python3 scripts/improve_recipes.py
python3 scripts/nutrition_engine.py
python3 scripts/fatty_liver_score.py
python3 scripts/build_index.py
python3 scripts/build_web.py
python3 scripts/build_insights.py
echo "Pipeline complete."
