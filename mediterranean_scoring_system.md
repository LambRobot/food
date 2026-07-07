# Mediterranean-Diet Recipe Scoring System

*Companion to `mediterranean_diet_wiki.md`. This document defines a transparent, reproducible algorithm for scoring how well a recipe fits the Mediterranean eating pattern. It is implemented in `score_recipes.py` and its outputs are `recipe_mediterranean_scores.json` / `.md`.*

---

## 1. Design goals

- **Grounded** in the science (Section 5 of the wiki — the Trichopoulou MDS directions) and the pyramid tiers.
- **Ingredient-level transparency:** every recipe shows *which* ingredients helped or hurt, and *how much* (a severity measure), exactly as requested.
- **Reproducible & deterministic:** a rules engine, not a black box. Re-running gives identical results and every point is traceable.
- **Method-aware:** rewards olive-oil sautéing/roasting/grilling; penalizes deep-frying and butter/cream cooking.

---

## 2. The 0–100 score

Every recipe starts at a **neutral base of 50** and is moved up by beneficial ingredients and down by detrimental ones, then clamped to `[0, 100]`.

```
score = clamp( 50 + Σ(positive contributions) − Σ(negative contributions), 0, 100 )
```

Contributions are **capped per category** so a recipe can't run away by, say, listing ten vegetables, and so no single bad ingredient alone tanks an otherwise balanced dish beyond its due.

### Letter grades

| Score | Grade | Meaning |
|---|---|---|
| 85–100 | **A** | Core Mediterranean — eat freely |
| 70–84 | **B** | Mediterranean-friendly — a regular in the rotation |
| 55–69 | **C** | Moderate — fine occasionally / with easy tweaks |
| 40–54 | **D** | Off-pattern — occasional treat only |
| 0–39  | **F** | Not Mediterranean — rare indulgence |

---

## 3. Positive ingredient tiers (what helps)

Each beneficial ingredient is tagged with a **positive tier** and point value. Per-category caps in parentheses.

| Tier | Examples | Points (each) | Cap |
|---|---|---|---|
| **SIGNATURE ⭐** | Extra-virgin olive oil | +10 | 10 |
| **SIGNATURE ⭐** | Legumes (lentils, chickpeas, beans, fava, peas) | +12 | 12 |
| **SIGNATURE ⭐** | Oily fish (salmon, sardines, mackerel, anchovy, tuna) | +12 | 12 |
| **GOOD ✓** | White fish & seafood (cod, shrimp, squid, mussels…) | +9 | 12 (shared w/ fish) |
| **GOOD ✓** | Whole grains (bulgur, farro, oats, brown/wild rice, quinoa, whole-wheat) | +8 | 8 |
| **GOOD ✓** | Vegetables (non-starchy) | +2.5 | 15 |
| **GOOD ✓** | Nuts & seeds (walnuts, almonds, tahini…) | +3 | 6 |
| **GOOD ✓** | Fruit | +2 | 6 |
| **MINOR +** | Herbs, spices, garlic, onion | +1 | 4 |
| **MINOR +** | Poultry (preferred over red meat) | +3 | 3 |
| **MINOR +** | Plain yogurt, modest traditional cheese, olives, avocado | +2 | 4 |

---

## 4. Negative ingredient tiers (what hurts) — the "measure" of bad

The severity measure the user asked for. Ordered worst-first.

| Severity | Examples | Points (each, before quantity adj.) | Cap |
|---|---|---|---|
| **SEVERE 🔴** ("really bad") | Processed/cured/smoked meat: bacon, ham, sausage, salami, chorizo, pepperoni, hot dog, prosciutto, pancetta, andouille, lardons | −14 | −24 |
| **SEVERE 🔴** | Deep-frying / frying in non-olive fat (method) | −10 | (method) |
| **SEVERE 🔴** | Sugary base / large added sugar as a main component (desserts, syrups, sweetened condensed milk, soda) | −8 | −16 |
| **HIGH 🟠** ("bad, limit") | Red meat: beef, pork, lamb, veal | −9 | −18 |
| **HIGH 🟠** | Butter, cream, heavy/sour cream, lard, shortening, margarine | −7 | −14 |
| **HIGH 🟠** | Tropical/solid fats: coconut oil/milk, palm oil | −5 | −10 |
| **MODERATE 🟡** ("not great / don't exceed") | Refined grains: white flour, white bread/rice/pasta | −5 | −10 |
| **MODERATE 🟡** | Cheese-heavy dish (cheese as the main event) | −5 | −5 |
| **MODERATE 🟡** | Added sugar in modest amounts | −3 | −6 |
| **MODERATE 🟡** | High-sodium: soy sauce, fish sauce, bouillon, heavy salt | −3 | −6 |
| **MODERATE 🟡** | Mayonnaise / creamy dressing | −3 | −6 |
| **MILD ⚪** ("minor") | Neutral seed oils (canola, vegetable, sunflower) used instead of olive oil | −2 | −4 |
| **MILD ⚪** | White potato as the primary starch | −2 | −4 |
| **MILD ⚪** | Spirits/liqueurs | −2 | −4 |

### Quantity adjustment ("as a condiment")
The Mediterranean pattern tolerates small amounts of otherwise-discouraged foods ("use meat as a condiment"). So each **penalty** is scaled by the amount detected in the ingredient line:

- **Small / condiment amount** (e.g., "1 tbsp", "1 tsp", "pinch", "1 clove", "for garnish", "1 slice") → penalty × **0.5**
- **Large amount** (e.g., "cup(s)", "lb / pound", "kg", "500 g") → penalty × **1.25**
- Otherwise → × **1.0**

Positives are not amount-scaled (presence is what signals the pattern), keeping the system simple and legible.

---

## 5. Category / whole-recipe modifiers

Applied after ingredient scoring, small nudges based on the dish as a whole:

- **Dessert/sweet recipe** (category or name indicates cake, cookie, ice cream, pastry, etc.): floor the expectation — desserts are inherently off-pattern, so a small extra −4 unless it's fruit/nut based.
- **Plant-only recipe** (no meat/fish/poultry, has vegetables or legumes): +4 vegetarian-Mediterranean bonus.
- **Fish or seafood main + olive oil + vegetables present:** +4 "textbook Mediterranean plate" bonus.
- **Refined grain present but a whole-grain alternative also present:** refined penalty halved.

---

## 6. What each recipe's report contains

For every recipe the output records:

1. **Score (0–100)** and **letter grade**.
2. **`good_ingredients`** — list of `{ingredient, tier, note}` (SIGNATURE / GOOD / MINOR).
3. **`bad_ingredients`** — list of `{ingredient, severity, note}` (SEVERE / HIGH / MODERATE / MILD) — the "how bad" measure.
4. **`comment`** — a short human verdict.
5. **`suggestions`** — concrete Mediterranean swaps (e.g., "use olive oil instead of butter", "swap white rice → brown rice", "make meat a condiment, not the base").
6. **`breakdown`** — the raw positive/negative point tallies for full traceability.

---

## 7. Limitations (honesty)

- Scoring reads **ingredient text only** — it can't perfectly judge quantities or true portion sizes, so the quantity adjustment is a heuristic.
- Keyword matching can miss unusual spellings or misclassify (e.g., "butternut squash" must not match "butter"); the lexicon uses word-boundary and negative-lookahead guards, but edge cases remain.
- The score rates **pattern fit, not overall healthiness or tastiness** — a fried-fish dish and a fruit tart are both "off-pattern" for different reasons.
- Cultural dishes that are traditionally Mediterranean but meat-forward (e.g., a lamb stew) are penalized on frequency grounds even though they belong in the cuisine — the score reflects *how often to eat it*, per the pyramid.
