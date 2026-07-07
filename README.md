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
│   ├── all_recipes.json                # All 293 recipes, structured (best for AI parsing)
│   ├── all_recipes.md                  # All 293 recipes, human-readable
│   ├── recipe_mediterranean_scores.json# Per-recipe score + graded ingredient analysis
│   └── recipe_mediterranean_scores.md  # Human-readable scorecards & leaderboard
├── scripts/
│   ├── parse_recipes.py                # Paprika HTML export  →  all_recipes.{json,md}
│   └── score_recipes.py                # all_recipes.json     →  recipe_mediterranean_scores.{json,md}
└── source/
    └── paprika-export/                 # The raw Paprika HTML export (source of truth)
```

## The recipe collection

**293 recipes** parsed from a Paprika export. Each carries: name, categories, prep/cook/total time,
servings, source + URL, description, ingredients, directions, notes, and nutrition where available.
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

## Reproducing

```bash
python3 scripts/parse_recipes.py     # regenerates data/all_recipes.{json,md}
python3 scripts/score_recipes.py     # regenerates data/recipe_mediterranean_scores.{json,md}
```

No dependencies beyond the Python standard library.

## Notes & limitations

- Scoring reads ingredient text, so it estimates rather than measures portions (hence the quantity
  heuristic). Non-English recipes (~40) have lighter lexicon coverage than English.
- The score rates **pattern fit, not overall healthiness or taste** — a fried-fish dish and a fruit
  tart are both "off-pattern" for different reasons.
- Traditionally-Mediterranean but meat-forward dishes (e.g. lamb tagine) are scored on *frequency*
  fit, per the food pyramid, so they land mid-grade even though they belong to the cuisine.
