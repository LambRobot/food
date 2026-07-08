# Known Issues, Limitations & Reliability Roadmap

*A candid debrief of everything built so far (recipe parsing → Mediterranean scoring → improvements → nutrition/health engine → index), the limitations of each layer, and a prioritized plan to make the whole system more reliable. Last updated 2026-07-07.*

---

## 0. What exists today

| Layer | Artifact | Status |
|---|---|---|
| Recipe parsing | `all_recipes.{json,md}` (293 recipes) | Solid — clean Paprika microdata |
| Mediterranean scoring | `recipe_mediterranean_scores.{json,md}` | Solid — transparent rules engine |
| Improved versions | `recipe_improvements.{json,md}` (≤3 swaps) | Solid |
| Nutrition + 4 health scores | `recipe_nutrition.{json,md}` | Good, with known estimation limits |
| Join table | `index.{json,md}` | Solid — all dims keyed by `id` |

All dimensions share a stable `id`. The nutrition engine is offline/deterministic on a committed USDA subset.

---

## 1. Known issues & limitations, by layer

### 1.1 Source data (the hardest constraint — we don't control it)
- **Servings are inconsistent/absent.** "Serving: 1" (means the whole dish), "6-835", "about 2 cups", or missing entirely. We parse heuristically and *flag* the ambiguous ones, but per-serving figures inherit this noise. **This is the single biggest source of per-serving error.**
- **Vague quantities.** "a big colander of greens", "salt to taste", "1 pack of ground meat" — no reliable weight exists.
- **Redundant/alternate ingredient listings.** Some recipes list an ingredient twice (e.g. Chicken Biryani lists the rice/aromatics in both a summary and a detailed block) → double counting.
- **Non-English recipes (~40).** French/German/Belgian ingredient text is only partially matched.
- **Personal/edge recipes.** Two "Dog Food" entries, curing recipes (smoked salmon, bacon) where salt/sugar is rinsed off, and non-dish entries.

### 1.2 Mediterranean scoring
- **Keyword lexicon, not semantics.** Misspellings, novel phrasings, or non-English terms can be missed. We've patched many (French meats, "ground meat", "half and half"), but coverage is finite.
- **Frequency vs. single-dish framing.** A lamb tagine is penalized on "eat red meat rarely" grounds even though it's a legitimate Mediterranean dish — the score rates *how often to eat it*, which can read as harsh.
- **Quantity is heuristic.** Penalties scale by rough amount detection ("condiment" leniency), not true grams.

### 1.3 Improvement engine
- **Swaps are ingredient substitutions, not recipe re-engineering.** They don't rebalance cooking method or proportions.
- **Approximate deltas.** Re-scored honestly, but the improved recipe's *taste/feasibility* isn't judged.

### 1.4 Nutrition engine — matching (biggest accuracy lever)
- **Heuristic + curated overrides.** ~92% of ingredient lines match; the rest are the long tail. Wrong matches still happen for unusual descriptors (audits caught "stew meat"→"Meat extender", "beer"→"Beerwurst", chicken→liver — all fixed, but the class of bug persists for un-audited items).
- **Raw vs. cooked / drained.** Canned/cooked legumes vs. raw dry beans differ ~3× in calorie density; we override the common ones but not all. Dried legumes *measured dry* are matched to cooked per-100g (undercount).
- **USDA SR Legacy gaps.** Newer foods (broccolini, some ethnic ingredients) aren't present → unmatched.
- **No branded/mixed-dish data.** We deliberately excluded FNDDS/Branded (size); mixed convenience items match poorly.

### 1.5 Nutrition engine — quantity → grams
- **Density & count fallbacks are typical values, not per-food.** Volume→grams uses USDA portions where available, else a density table; counts ("2 onions") use average item weights. Real items vary ±30%.
- **Deep-fry oil, curing salt, marinades** are consumed only partially; we approximate frying absorption (~12%) and flag high-sodium cures, but marinades/brines are still summed in full.
- **Unrecognized units** default to low-confidence guesses (flagged, but present).

### 1.6 Nutrition engine — cooking & scores
- **Retention factors are representative, not per-food.** Applied by cooking method from a compact table (USDA Release-6-derived), not the full per-food/per-nutrient table (which lives in a PDF, not the bulk CSV). Also assumes matched foods are "raw"; foods already matched as "cooked" get retention applied twice in principle.
- **HEI-2020 is approximate.** Moderation components (sodium, sat fat, sugar, refined grain) are nutrient-accurate; adequacy components use gram→cup/oz-equivalent proxies instead of the USDA FPED database, and "added sugar" is approximated by total sugar (overestimate for fruit-containing dishes).
- **Nutri-Score inherits its known quirks** (rewards veg content even in calorie-dense dishes, e.g. moussaka scores A). Not a bug — a property of the algorithm; NOVA/HEI/Mediterranean provide the counterweight.
- **NOVA is a heuristic guess** from ingredient keywords, not a rigorous classification.

### 1.7 Cross-cutting
- **No ground-truth validation.** We've never compared outputs to lab-analyzed or professionally-computed nutrition for even a handful of these recipes, so absolute accuracy is asserted (±10–25%) rather than measured.
- **Confidence is a proxy** (match coverage × gram-estimate quality), not a calibrated probability.
- **No automated regression tests.** Bugs were found by manual audits; a fix could silently regress another recipe.

---

## 2. How reliability was pursued so far
- Two manual audits (~45 recipes) that fixed ~15 systematic parsing/matching bugs.
- Automated anomaly scans (implausible kcal/fiber/sodium/protein) to surface outliers.
- Per-recipe **coverage/confidence** flags and unmatched-ingredient lists, so low-trust results are never presented as precise.
- Cross-framework coherence check: Nutri-Score correlates monotonically with the Mediterranean grade (independent validation).

---

## 3. Reliability roadmap (prioritized by impact ÷ effort)

### Tier 1 — highest leverage
1. **Golden-set regression tests.** ✅ **DONE** — `scripts/test_engine.py` + `tests/golden.json`: cross-file id integrity, per-recipe invariants (no negatives, calories reconcile with macros, per-serving×servings=total), 24 hand-verified golden anchors (±30% tolerance), and an anomaly gate that *fails* on impossible values and *warns* on suspicious-but-possible. Run it after any change.
2. **Ground-truth calibration.** ✅ **DONE** — `scripts/calibrate_nutrition.py` (→ `data/nutrition_calibration.md`) compares the engine against the **original published nutrition** scraped from each recipe's source site (96 in-scope recipes carry it — genuinely independent). **Measured results:** serving-aligned energy median error **24%** (52% within 25%); macro-distribution (serving-independent P/C/F %) median **8.0 percentage points** — composition is accurate. **Confidence is validated:** median energy error high **22%** < medium **41%** < low **63%** (monotonic — the flag means something). The energy error is inflated by serving-basis disagreements (some sources publish per-whole-recipe or per-piece); the 8 pp macro figure is the cleaner signal that the matching is sound.
3. **Servings resolver.** ✅ **DONE** — source servings are now **ignored entirely** (kept only as `source_servings` for reference). Servings are computed from total edible weight ÷ a standard portion size by dish type (main 400 g, soup/stew 450 g, side 130 g, sauce 55 g, dessert 115 g, bread 70 g, drink 250 ml). Independently validated: e.g. Guinness Stew resolves to 11 vs. the source's 10. Remaining edge cases: appetizers/dumplings classified as "main" get too few servings (flagged as warnings).

### Tier 2 — accuracy depth
4. **Better ingredient matching.** Move from keyword-heuristic to (a) the NYT/`ingredient-parser-nlp` parser for cleaner name/qty extraction, and (b) fuzzy/embedding match with a confidence threshold; auto-generate an "unmatched & low-confidence" worklist to expand `ingredient_overrides.json` systematically instead of reactively.
5. **Cooked/drained/raw normalization.** Encode a rule: legumes/grains stated dry vs. cooked, canned drained weights, and prefer cooked USDA forms for stews/bakes. Removes the recurring 3× legume error class.
6. **Add USDA FNDDS (Survey) portions & mixed dishes.** Its `food_portion` table is the richest household-measure→gram source and it has prepared/mixed items — improves both matching and unit conversion (cost: 1.6 GB source, but we extract only what's used).

### Tier 3 — completeness & polish
7. **Real retention factors.** Parse USDA Release-6 (retn06.pdf) into a per-food-group × nutrient table; apply only to raw-matched ingredients to avoid double-discounting.
8. **True HEI-2020 via FPED.** Map ingredients to Food Pattern Equivalents (cup/oz-eq) for exact adequacy components; separate added vs. intrinsic sugar.
9. **Non-English coverage.** Add a French/German→English ingredient alias layer (or CIQUAL/German BLS composition data) to lift the ~40 non-English recipes out of low-confidence.
10. **Marinade/brine/oil-for-frying model.** Generalize the "partially consumed" logic (frying absorption, drained cures, discarded marinade) with per-technique fractions.

### Tier 4 — product/UX
11. **Uncertainty ranges, not point values.** Present "≈420 kcal (±20%)" and propagate ingredient-level confidence into a per-recipe band.
12. **Human-in-the-loop correction file.** A small `data/manual_corrections.json` (by `id`) that overrides engine output for known-wrong recipes, applied last — captures expert fixes permanently.
13. **CI on the whole pipeline.** Run parse→score→improve→nutrition→index + anomaly scan + golden tests on every change; fail on new anomalies.

---

## 4. Recommended next step
Start with **Tier 1** — regression tests + a small ground-truth calibration + the servings resolver. Together they convert the current "audited and plausible" state into "measured, monitored, and self-protecting," which is the foundation every later accuracy improvement should build on. Tier 2 (matching + cooked/drained normalization) is the biggest remaining *accuracy* gain after that.
