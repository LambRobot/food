# Recipe Nutrition & Health Scoring — Methodology Wiki

*Compiled 2026-07-07 from authoritative sources (USDA FoodData Central & ARS, Nutri-Score/Santé Publique France, the Nutrient-Rich Foods Index literature, NOVA/Monteiro). Reference basis for the nutrition/health dimension of the recipe collection. Companion to `nutrition_engine_plan.md`.*

---

## 1. The problem in one sentence

Given a recipe (a list of ingredient lines + a serving count), estimate its **nutrition** (calories, macronutrients, key micronutrients per serving) and derive one or more **health scores** — the same way a registered dietitian or a nutrition-analysis product does it.

The professional pipeline is always the same four steps:

```
parse ingredient line → match to a food-composition record → convert amount to grams
   → look up nutrients per 100 g → sum over ingredients → apply cooking yield/retention
   → divide by servings → per-serving nutrition → compute health score(s)
```

Everything below is the evidence for how each step is done "properly."

---

## 2. Food-composition databases (the source of truth)

Nutrition numbers come from a **food-composition database** — laboratory-analyzed nutrient values per 100 g of food. The professional standard in the US:

### USDA FoodData Central (FDC) — the reference, and it's free
Maintained by the USDA Agricultural Research Service. Five data types, each suited to a purpose:

| Data type | What it is | Best for |
|---|---|---|
| **Foundation Foods** | Lab-analyzed basic foods with full metadata (samples, methods, provenance) | Highest-quality raw/whole ingredients |
| **SR Legacy** (2018, final) | ~7,800 foods, the classic "Standard Reference"; broad coverage incl. cooked forms | Workhorse for general ingredient lookup |
| **FNDDS / Survey Foods** | Foods as eaten in NHANES "What We Eat in America"; includes mixed dishes & **portion weights** | Household-measure gram weights, prepared dishes |
| **Branded Foods** | ~250k+ commercial products from labels | Packaged/branded items |
| **Experimental** | Research foods | Niche |

**Access options**
- **API:** free with a data.gov key. Endpoints: `/foods/search`, `/food/{fdcId}`, `/foods` (batch), `/foods/list`. **Rate limit 1,000 req/hr** (DEMO_KEY only 30/hr). Returns full nutrient arrays per food.
- **Bulk download:** full CSV/JSON datasets for **offline use** — no key, no rate limit, fully reproducible. SR Legacy download includes the `food_portion` table (gram weight per household measure, e.g. "1 cup = 240 g").

### International equivalents (for non-US coverage)
- **McCance & Widdowson's** (UK), **CIQUAL** (France, free), **CNF** (Canada), **EuroFIR** (European aggregator). Useful because this collection has French/Belgian/German dishes.

### Commercial APIs (turn-key but paid)
| Provider | Note | Price (approx.) |
|---|---|---|
| **Edamam** | Nutrition + recipe analysis API; does the whole pipeline | from ~$299/mo (free tier limited) |
| **Nutritionix** | Restaurant/branded focus | from ~$1,850/mo |
| **Spoonacular** | Recipe-analysis focused | free tier → ~$149/mo |
| **Open Food Facts** | Free, crowdsourced, branded-product focused (2.5M products) | free |

**Takeaway:** USDA FDC is the professional, authoritative, free backbone. Commercial APIs mainly *package* the same kind of data plus their own matching. For a reproducible, offline, deterministic engine (matching this repo's philosophy), **USDA FDC data (offline subset or cached API lookups) is the right foundation.**

---

## 3. Step 1 — Parsing the ingredient line

Turn `"2 ½ cups whole-wheat flour, sifted"` into `{qty: 2.5, unit: cup, item: "whole-wheat flour", prep: "sifted"}`.

- **Tools:** `ingredient-parser-nlp` (Python, MIT, sequence model trained on 81k sentences, ~95.6% sentence accuracy) extracts name/amount/unit/prep/confidence. The **NYT Ingredient Phrase Tagger** is the classic reference implementation.
- **Note:** these parsers **do not convert to grams** — they only structure the text. Unit→gram is our job (Step 3).
- **Reality:** ingredient lines are messy — implicit quantities ("salt to taste"), ranges, "1 (14 oz) can", garnishes. A parser plus sensible fallbacks is required; some lines contribute 0 (e.g. "for serving").

---

## 4. Step 2 — Matching to a food record

Map `"whole-wheat flour"` → a specific FDC food (e.g. *Flour, whole wheat* fdcId 168944). This is the accuracy-critical, hardest step.

- **Fuzzy string match** of the parsed name against food descriptions (token overlap, edit distance) — fast but error-prone (e.g. "cream" → "cream of tartar").
- **Curated alias map** — a hand-verified `ingredient → fdcId` table for the recipe collection's actual vocabulary. Far more accurate; feasible because a 293-recipe collection has a **bounded ingredient vocabulary** (a few hundred base ingredients after normalization).
- **Hybrid (recommended):** curated map for the common/ambiguous items, fuzzy match as fallback, and **log every unmatched ingredient** so coverage is transparent (never silently score 0).

---

## 5. Step 3 — Amount → grams

Nutrients are stored per 100 g, so every ingredient amount must become grams.

- **Mass units** (g, kg, oz, lb): direct conversion (1 oz = 28.35 g, 1 lb = 453.6 g).
- **Volume units** (cup, tbsp, tsp, ml): need **density** (g/ml) or a **portion weight**. Two sources:
  - USDA `food_portion` / FNDDS portion tables: "1 cup, chopped = 150 g" per food.
  - Standard densities for common items (water/liquids ≈ 1.0; oil ≈ 0.92; flour ≈ 0.53 g/ml; sugar ≈ 0.85).
- **Count units** ("2 eggs", "1 onion"): need an average item weight (1 large egg ≈ 50 g; 1 medium onion ≈ 110 g).
- **Vague amounts** ("a pinch", "to taste", "for garnish"): assign a small nominal weight or 0.

This conversion layer is the second-biggest accuracy lever after matching.

---

## 6. Step 4 — Cooking yield & nutrient retention (the "cooked recipe" correction)

Raw-ingredient sums overstate/understate a cooked dish because water and fat change, and heat destroys some micronutrients. USDA defines two correction factors (this is exactly how USDA computes recipes — see their Chocolate Cake worked example):

- **Yield factor** — weight change from cooking (water/fat loss or gain). `Yield% = 100 × (cooked weight / raw weight)`. Concentrates or dilutes nutrients per gram; essential for correct **per-serving** weight.
- **Nutrient retention factor** — fraction of a nutrient surviving cooking, via the **True Retention Method**: `%TR = (N_cooked × G_cooked) / (N_raw × G_raw) × 100`. USDA **Table of Nutrient Retention Factors (Release 6)** covers 16 vitamins, 8 minerals, and alcohol for ~290 foods.

**Pragmatic stance:** yield/retention mainly affect **micronutrients and water weight**; **calories and macros are largely conserved** (protein/fat/carb aren't destroyed by normal cooking). So a v1 that reports calories + macros without retention is already reasonably accurate; retention factors are a v2 refinement for vitamins/minerals.

---

## 7. Per-serving & the accuracy reality

- Divide totals by the recipe's `servings` (already parsed in `all_recipes.json`; fall back to a default if missing).
- **Honest accuracy:** even professional recipe-analysis tools are estimates. Sources of error: ingredient matching, unit→gram assumptions, "to taste" amounts, ingredient variability, cooking losses. Real-world agreement with lab analysis is typically **±10–25%**. The engine must surface a **confidence/coverage metric** (what % of ingredients by weight were matched) rather than implying false precision.

---

## 8. Health-scoring frameworks (rating the nutrition)

Raw numbers aren't a verdict. Established, validated frameworks turn nutrition into a health rating. Each answers a different question:

### Nutri-Score — "overall front-of-pack quality, A–E" (recommended primary)
- Computed **per 100 g**. **Negative** points from energy, sugars, saturated fat, sodium; **positive** points from fruit/veg/legumes/nuts %, fibre, protein.
- Continuous scale ≈ **−15 (best) to +40 (worst)**, bucketed into **A–E** (green→red). Separate thresholds for beverages and for fats/oils/nuts.
- Best-known, validated against health outcomes, simple, and consumer-facing. 2023 update refined sugar/salt/fibre handling and dairy/oil categories.

### NRF9.3 (Nutrient-Rich Foods Index) — "nutrient density" (recommended secondary)
- `NRF9.3 = Σ(%DV of 9 nutrients to encourage) − Σ(%DV of 3 to limit)`, capped and expressed **per 100 kcal** (or per 100 g).
- Encourage: protein, fibre, vitamins A, C, E, calcium, iron, magnesium, potassium. Limit: saturated fat, added sugar, sodium.
- Gives a **continuous nutrient-density number** — great for ranking recipes by "nutrition per calorie."

### NOVA — "degree of processing, 1–4" (recommended context flag)
- Not nutrient-based: classifies by processing. **1** unprocessed/minimally processed, **2** culinary ingredients (oil, sugar, salt), **3** processed foods, **4** ultra-processed.
- For home recipes cooked from whole ingredients most land **1–3**; a strong ultra-processed signal (e.g. condensed soup, processed cheese product) flags NOVA 4. Complements Nutri-Score (a food can be Nutri-Score B but NOVA 4).

### HEI-2020 — "alignment with US Dietary Guidelines, 0–100" (optional)
- 13 components scored **per 1,000 kcal**; designed for whole **diets** but adaptable to a recipe. More complex; better as a later addition.

### Others (for reference)
- **WHO / Ofcom (UK) nutrient profile model** — regulatory (marketing-to-children) thresholds.
- **Health Star Rating** (Australia/NZ), **Glycemic Index/Load** (blood-sugar impact; needs GI tables).

**How these complement the existing Mediterranean score:** the Mediterranean score already rates *dietary-pattern fit*. Nutri-Score/NRF add *nutrient quality*, NOVA adds *processing*. Together they give a recipe a rounded health picture from independent, validated angles.

---

## 9. Sources

- [USDA FoodData Central — API Guide](https://fdc.nal.usda.gov/api-guide/) · [Foundation Foods Documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/) · [Downloadable Datasets](https://fdc.nal.usda.gov/download-datasets/)
- [USDA Table of Nutrient Retention Factors, Release 6 (PDF)](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/retn06.pdf) · [USDA recipe calc worked example — Chocolate Cake (PDF)](https://www.ars.usda.gov/ARSUserFiles/80400525/Articles/ndbc26_recipe.pdf)
- [ingredient-parser-nlp (PyPI)](https://pypi.org/project/ingredient-parser-nlp/) · [NYT Ingredient Phrase Tagger](https://github.com/nytimes/ingredient-phrase-tagger)
- [Two Dimensions of Nutritional Value: Nutri-Score and NOVA (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8399905/) · [Nutri-Score updated algorithm & NOVA complementarity (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10897572/)
- [Development and Validation of the Nutrient-Rich Foods Index (J. Nutrition)](https://jn.nutrition.org/article/S0022-3166(22)06842-0/fulltext)
- [Nutrition API comparison (Edamam/Nutritionix/Spoonacular/USDA/OFF)](https://about.greenchoicenow.com/nutrition-data-api-comparison)
