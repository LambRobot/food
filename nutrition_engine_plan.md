# Nutrition & Health Engine — Design Plan

*Grounded in `nutrition_methodology_wiki.md`. Status: **v1 implemented.** Decisions taken: data source = **USDA bulk download** (SR Legacy + Foundation, extracted to a committed compact reference); scores = **all four** (Nutri-Score live, NRF9.3 live, NOVA live, HEI-2020 scaffolded); scope = **full** (macros + micronutrients). Cooking yield/retention factors remain the one deferred item (USDA retention values are in a separate PDF table, not the bulk CSV).*

## Implemented pipeline (v1)
`scripts/fetch_usda.sh` → `scripts/build_nutrition_reference.py` (→ `data/usda_reference.json`, 8.2k foods) → `scripts/nutrition_engine.py` (→ `data/recipe_nutrition.{json,md}`) → registered in `build_index.py`. Matching uses `scripts/nutrition_match.py` (heuristic + `data/ingredient_overrides.json`). Result: 293 recipes scored, 188 high-confidence, median 334 kcal/serving; Nutri-Score correlates monotonically with the Mediterranean grade (independent validation).

---

## 1. Goal

A small, reproducible engine that takes a recipe (ingredient lines + servings, already in `all_recipes.json`) and outputs, **per serving**:

- **Calories** and **macronutrients** — protein, carbohydrate, fibre, sugar, fat, saturated fat, sodium (and later key micronutrients).
- One or more **health scores** from validated frameworks (Nutri-Score, NRF9.3 nutrient density, NOVA processing).
- A **coverage/confidence** figure — the % of the recipe (by estimated weight) that was actually matched to nutrition data — so we never imply false precision.

It becomes a new `id`-keyed dimension (`data/recipe_nutrition.{json,md}`) registered in `index.json`, exactly like the Mediterranean dimension.

## 2. Architecture (the pipeline)

```
all_recipes.json
      │  for each recipe, for each ingredient line:
      ▼
[1 parse]      "1½ cups whole-wheat flour, sifted" → {qty:1.5, unit:cup, name:"whole-wheat flour"}
      ▼
[2 match]      name → nutrition_reference entry (curated alias, else fuzzy)   ── logs misses
      ▼
[3 to grams]   qty+unit+name → grams  (mass | density/volume | per-count weight)
      ▼
[4 nutrients]  grams × per-100g nutrients  → this ingredient's contribution
      ▼           (v2: × yield & retention factors)
[5 sum]        Σ ingredients → recipe totals
      ▼
[6 per serving] ÷ servings → per-serving nutrition + coverage%
      ▼
[7 score]      per-100g/per-serving → Nutri-Score (+ NRF9.3, NOVA)
      ▼
data/recipe_nutrition.{json,md}   →   registered in index.json
```

Each stage is a testable function; stages 2–3 are where accuracy is won or lost.

## 3. The key building block: a local nutrition reference table

Runtime should be **offline and deterministic** (like every other script here). So the engine reads a committed **`data/nutrition_reference.json`**: for each base ingredient, its USDA-sourced per-100 g nutrients + a default gram weight per common unit.

```jsonc
{
  "olive oil":        { "fdc_id": 171413, "per_100g": {"kcal":884,"protein":0,"carb":0,"fiber":0,
                        "sugar":0,"fat":100,"sat_fat":13.8,"sodium":2}, "g_per":{"tbsp":13.5,"cup":216} },
  "whole-wheat flour":{ "fdc_id": 168944, "per_100g": {"kcal":340,"protein":13.2, ... }, "g_per":{"cup":120} },
  ...
}
```

**How this table gets populated** is the main decision (Section 6). The recipe collection has a **bounded vocabulary** — an estimated ~250–400 distinct base ingredients after normalization — so a one-time populate is very tractable.

## 4. Ingredient matching (accuracy-critical)

Hybrid, transparent:
1. **Normalize** the parsed name (lowercase, strip prep words, singularize; reuse logic already in `score_recipes.py`).
2. **Curated alias map** (`data/ingredient_aliases.json`): hand-verified `variant → canonical` for the collection's common/ambiguous items (e.g. "EVOO"/"extra-virgin olive oil"/"huile d'olive" → `olive oil`). Also fixes the French/German items.
3. **Fuzzy fallback** for the long tail (token overlap; guarded against known traps like cream≠cream-of-tartar).
4. **Log every unmatched ingredient** and compute **coverage%** = matched weight ÷ total estimated weight. Recipes below a coverage threshold are marked low-confidence rather than shown as precise.

## 5. Output schema (per recipe)

```jsonc
{
  "id": "winter-tagine",
  "servings": 6,
  "per_serving": { "kcal":420, "protein_g":14, "carb_g":58, "fiber_g":11,
                   "sugar_g":12, "fat_g":16, "sat_fat_g":2.4, "sodium_mg":480 },
  "per_100g":   { ... },                // needed for Nutri-Score
  "health_scores": {
    "nutri_score": { "grade":"A", "points":-2 },
    "nrf9_3": 34.5,                      // nutrient density
    "nova_group": 1                      // processing
  },
  "coverage": { "matched_pct": 0.94, "unmatched": ["saffron"], "confidence":"high" }
}
```

## 6. Decisions needed before building

**A. Where nutrition numbers come from** (populates `nutrition_reference.json`):
- **USDA FDC API, cached** *(recommended)* — one build-time script enumerates the collection's unique ingredients, queries USDA (free data.gov key, 1,000/hr), writes the reference table; runtime stays offline. Most authoritative; **needs a free API key**.
- **USDA bulk download** — download SR Legacy CSVs, build the table locally. No key; larger, one-time data wrangling.
- **Curated starter table** — seed per-100 g values for the common ingredients now (from standard references), refine later. Fastest to a working v1; provenance weaker.
- **Paid API (Edamam/Spoonacular)** — turn-key recipe analysis, but $ and licensing; against the offline/reproducible grain.

**B. Which health scores** — Nutri-Score (primary), NRF9.3 (nutrient density), NOVA (processing), HEI-2020 (diet-guideline alignment).

**C. v1 scope** — **calories + macros + Nutri-Score** first (macros are well-conserved in cooking, so this is accurate and fast), then add micronutrients + retention factors + NRF9.3/NOVA in v2. Or go full-fat in one pass.

## 7. Accuracy & honesty commitments
- Always publish **coverage%** and list unmatched ingredients; never silently score 0.
- State the **±10–25% estimate** caveat; don't over-round (e.g. "≈420 kcal", not "418.3").
- v1 skips micronutrient retention (macros barely change with cooking); note it as a known simplification.

## 8. Reuse from the existing repo
- `all_recipes.json` already has parsed `ingredients`, `servings`, and stable `id`.
- Ingredient normalization / French-German aliases already exist in `score_recipes.py` — factor into a shared helper.
- Same dimension pattern: `scripts/nutrition_engine.py` → `data/recipe_nutrition.{json,md}` → register in `build_index.py`.

## 9. Proposed phases
1. **v1** — reference table for the collection's vocabulary; parse→grams→macros; Nutri-Score; coverage. Ship `recipe_nutrition.{json,md}`.
2. **v2** — micronutrients (vitamins/minerals), USDA yield + retention factors, NRF9.3, NOVA.
3. **v3** — combined "health snapshot" per recipe merging Mediterranean + Nutri-Score + NOVA; cross-collection analytics.
