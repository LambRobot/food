# 🍅 Food — Recipe Collection & Mediterranean-Diet Scoring

A personal recipe collection (exported from [Paprika](https://www.paprikaapp.com/)) compiled into
AI-friendly formats, plus a transparent system that scores every recipe for how well it fits the
**Mediterranean diet**.

## What's here

```
.
├── mediterranean_diet_wiki.md          # Reference wiki: the Mediterranean diet, researched & cited
├── mediterranean_scoring_system.md     # The 0–100 scoring methodology
├── data/
│   ├── index.json / index.md           # Canonical join table (id, cuisine, dish type, score, flags)
│   ├── all_recipes.json                # All 293 recipes, structured (best for AI parsing)
│   ├── all_recipes.md                  # All 293 recipes, human-readable
│   ├── recipe_mediterranean_scores.json# Per-recipe score + graded ingredient analysis
│   ├── recipe_mediterranean_scores.md  # Human-readable scorecards & leaderboard
│   ├── recipe_improvements.json        # "Improved" version of each recipe (≤3 swaps), re-scored
│   ├── recipe_improvements.md          # Human-readable before → after with swaps
│   ├── recipe_nutrition.json / .md     # Per-serving nutrition + health scores (USDA-based)
│   ├── usda_reference.json             # Compact USDA food table (built from bulk download)
│   └── ingredient_overrides.json       # Curated ingredient → USDA food overrides
├── scripts/
│   ├── parse_recipes.py                # Paprika HTML export  →  all_recipes.{json,md}
│   ├── score_recipes.py                # all_recipes.json     →  recipe_mediterranean_scores.{json,md}
│   ├── improve_recipes.py              # scores               →  recipe_improvements.{json,md}
│   ├── fetch_usda.sh                   # download USDA bulk CSVs → data/usda_src/ (git-ignored)
│   ├── build_nutrition_reference.py    # USDA CSVs             →  usda_reference.json
│   ├── nutrition_match.py              # ingredient → USDA food matcher (+ audit mode)
│   ├── nutrition_engine.py             # all_recipes + USDA    →  recipe_nutrition.{json,md}
│   └── build_index.py                  # everything           →  index.{json,md}
└── source/
    └── paprika-export/                 # The raw Paprika HTML export (source of truth)
```

## The recipe collection

**293 recipes** parsed from a Paprika export. Each carries a **stable `id`** (slug, for joining
future data), name, categories, prep/cook/total time, servings, source + URL, description,
ingredients, directions, notes, and nutrition where available. Baseline-hygiene flags:
`non_food` (e.g. the two "Dog Food" entries) and `duplicate_of` (id of the original when a
recipe appears twice). The score records add `is_dessert`.
The Paprika export uses clean [schema.org](https://schema.org/Recipe) microdata, so parsing is
field-accurate (accents, unicode fractions, and French/German/Thai text preserved).

## Mediterranean-diet scoring

Every recipe gets a **0–100 score** and an **A–F grade** based on how well its ingredients and
cooking method match the Mediterranean pattern (Harvard / Oldways pyramid / the Trichopoulou
Mediterranean Diet Score — all cited in the wiki).

Each recipe starts at a neutral **50**, then a transparent rules-engine moves it up or down:

- **Good ingredients** — ⭐ *signature* (olive oil, legumes, fish), ✓ *good* (vegetables, whole
  grains, nuts, fruit), + *minor* (herbs, poultry, yogurt).
- **Bad ingredients**, tagged by how far off-pattern they are:
  🔴 **SEVERE** (processed/cured meat, deep-frying, concentrated sugar) ·
  🟠 **HIGH** (red meat, butter/cream, coconut/palm fat) ·
  🟡 **MODERATE** (refined grains, heavy cheese, added sugar, high sodium) ·
  ⚪ **MILD** (neutral oils, white potato, spirits).

Penalties scale with quantity (a pinch of butter ≠ a cup), and every score comes with a comment,
highlighted good/bad ingredients, and concrete "make it more Mediterranean" swaps.

### "Mediterranean-ized" versions

`recipe_improvements.md` takes each recipe and applies **up to 3 Mediterranean swaps**, then
**re-scores the modified recipe** so the improved number is real, not estimated. The rules:

- Only *swap an existing bad ingredient or method* — butter/cream → olive oil or Greek yogurt,
  refined grain → whole grain, neutral oil → olive oil, drop cured meat, deep-fry → roast/sear,
  cut added sugar, reduce high-sodium sauces or heavy cheese.
- **Never add olive oil from nothing** — only substitute it for another fat.
- **Red meat is left alone** — it defines the dish, so it isn't "swappable."
- A swap is only applied if it *actually* raises the re-scored value.

Result: **238 of 293** recipes improve with ≤3 swaps (avg **+20 points**), and **195** move up a
letter grade. Biggest wins come from dropping cured meat and swapping cream → yogurt
(e.g. Cajun Gumbo 41→90, Grilled Tilapia Tacos 50→94). Aggressively swapping a dessert
(e.g. butter/flour/sugar in a cake) changes what the dish *is* — noted as a caveat in the file.

### Results across the collection

| Grade | Meaning | Count |
|---|---|---|
| **A** | Core Mediterranean | 8 |
| **B** | Mediterranean-friendly | 41 |
| **C** | Moderate | 78 |
| **D** | Off-pattern | 88 |
| **F** | Not Mediterranean | 78 |

Average score: **~52/100**. Top of the list is plant- and legume-forward (Winter Tagine, quinoa
salads, vegan chili); the bottom is butter/cream/cheese, processed meat, and dessert-heavy.

## The index — how to add more data later

`data/index.json` is the **canonical join table**. Every recipe has a stable `id`, and every
per-recipe data file is keyed by that `id`. The index also carries a transparent **cuisine** and
**dish-type** guess (a trailing `?` in `index.md` marks a guess not backed by an explicit category
tag) and the hygiene flags.

To add a new dimension (e.g. nutrition, cost, allergens, another diet score):

1. Write a `scripts/<dimension>.py` that reads `data/all_recipes.json`, keys on `id`, and emits
   `data/recipe_<dimension>.json` (same shape as the existing dimension files).
2. Register it in `DIMENSIONS` at the top of `scripts/build_index.py` and re-run it — the index
   then advertises the new file so anything consuming the collection can discover and join it.

Current dimensions: `mediterranean_score`, `mediterranean_improvement`, `nutrition`.

### Nutrition & health dimension

`data/recipe_nutrition.{json,md}` gives per-serving **calories, macros, and micronutrients** plus
validated **health scores** — computed the professional way (parse ingredient → match to a USDA
FoodData Central food → convert to grams → sum → per serving → score). It's fully offline: a compact
USDA reference (`usda_reference.json`, 8.2k foods) is built once from the bulk download
(`scripts/fetch_usda.sh` + `build_nutrition_reference.py`), then the engine runs against it.

- **Health scores:** Nutri-Score (A–E), NRF9.3 nutrient density, NOVA processing (1–4); HEI-2020 scaffolded.
- **Servings are self-computed**, not trusted from the (inconsistent) source: servings = total
  edible weight ÷ a standard portion size per dish type. The source value is kept as
  `source_servings` for reference. Both `per_serving` and `total_kcal` are provided.
- **Out-of-scope flag:** pet-food and curing/preserving recipes are marked `out_of_scope` so
  analyses can skip them.
- **Honesty:** every recipe carries a match-coverage **confidence** (high/medium/low) and unmatched
  ingredients. **Measured accuracy** (vs. 96 recipes' original published nutrition, via
  `scripts/calibrate_nutrition.py`): macro composition within ~8 percentage points; energy median
  ~22% (high-confidence 21% < medium 23% < low 79% — confidence is validated). See
  `data/nutrition_calibration.md` and `KNOWN_ISSUES_AND_ROADMAP.md`.
- **Regression tests:** `python3 scripts/test_engine.py` guards the whole pipeline (id integrity,
  invariants, golden anchors, anomaly gate) — run it after any change.
- **Validation:** Nutri-Score correlates monotonically with the independent Mediterranean grade
  (Med A → best Nutri-Score, Med F → worst).
- See `nutrition_methodology_wiki.md` (researched sources) and `nutrition_engine_plan.md` (design).

## Reproducing

```bash
python3 scripts/parse_recipes.py     # regenerates data/all_recipes.{json,md}
python3 scripts/score_recipes.py     # regenerates data/recipe_mediterranean_scores.{json,md}
python3 scripts/improve_recipes.py   # regenerates data/recipe_improvements.{json,md}
bash   scripts/fetch_usda.sh         # one-time: download USDA bulk CSVs (git-ignored)
python3 scripts/build_nutrition_reference.py  # rebuilds data/usda_reference.json
python3 scripts/nutrition_engine.py  # regenerates data/recipe_nutrition.{json,md}
python3 scripts/build_index.py       # regenerates data/index.{json,md}
```

No dependencies beyond the Python standard library.

## Notes & limitations

- Scoring reads ingredient text, so it estimates rather than measures portions (hence the quantity
  heuristic). Non-English recipes (~40) have lighter lexicon coverage than English.
- The score rates **pattern fit, not overall healthiness or taste** — a fried-fish dish and a fruit
  tart are both "off-pattern" for different reasons.
- Traditionally-Mediterranean but meat-forward dishes (e.g. lamb tagine) are scored on *frequency*
  fit, per the food pyramid, so they land mid-grade even though they belong to the cuisine.
