# Fatty Liver Disease (MASLD/NAFLD) — Dietary Reference Wiki

> **Disclaimer.** This document summarizes *published, evidence-based dietary guidance* for metabolic-dysfunction-associated steatotic liver disease (MASLD, formerly NAFLD) so it can inform a recipe **food-scoring tool**. It is **educational, not medical advice**. Anyone with fatty liver disease should work with their **hepatologist and a registered dietitian** — individual needs (medications, diabetes, cirrhosis stage, other conditions) change what's appropriate.

*Compiled 2026-07 from the 2024 EASL–EASD–EASO and AASLD guidelines, Mayo Clinic, and peer-reviewed reviews. Companion to a proposed "Fatty-Liver Fit" scoring dimension.*

---

## 1. The one-sentence summary

For fatty liver disease, the **Mediterranean diet is the #1 recommended eating pattern across every major guideline** — so your starting point was correct — but MASLD adds **condition-specific emphases**, above all: **cut added sugar/fructose and alcohol hard, limit saturated fat and refined carbs, and moderate total calories** (because even 5–10% weight loss measurably reduces liver fat).

---

## 2. Why fatty liver is different from "just eat healthy"

The liver turns **excess fructose and refined carbohydrate** into fat via *de novo lipogenesis* — fructose in particular bypasses the body's normal "I'm full" signals and is an unregulated feedstock for making liver fat. High sugar also drives **insulin resistance**, which further pushes the liver to store fat. This is why the single most impactful dietary lever for MASLD is **reducing added sugar (especially sugary drinks and high-fructose corn syrup)** — "reduced sugar consumption improves liver fat within weeks."

So relative to a generic healthy diet, MASLD guidance **up-weights** three things: **sugar/fructose control, alcohol avoidance, and calorie/weight management**.

---

## 3. Foods & nutrients to EMPHASIZE (protective)

| Item | Why it helps MASLD |
|---|---|
| **Oily fish & omega-3** (salmon, sardines, mackerel, anchovies) | Prevents hepatic fat accumulation; reduces steatosis |
| **Olive oil / MUFA** | The core Mediterranean fat; anti-inflammatory, replaces saturated fat |
| **Vegetables** (freely, cooked in olive oil) | Fiber + low energy density; improves insulin sensitivity |
| **Legumes** (lentils, chickpeas, beans) | Fiber + plant protein; steadies blood sugar |
| **Whole grains** (over refined) | Slow carbs; fiber; better glycemic response |
| **Nuts, seeds, avocado** | Healthy fats, fiber |
| **Whole fruit** (1–3 servings/day, *not* juice) | Fiber blunts the fructose; juice is rapidly-absorbed sugar → avoid |
| **Coffee (≥3 cups/day, caffeinated or decaf)** | Consistently associated with **less advanced liver disease and less fibrosis** — a genuinely liver-specific positive |
| **High total fiber** | Improves insulin sensitivity; stabilizes blood sugar |

---

## 4. Foods & nutrients to LIMIT or AVOID — with MASLD-specific severity

Ordered by how strongly the evidence implicates them in liver fat.

### SEVERE — the biggest liver-fat drivers
- **Added sugar & fructose**, especially **sugar-sweetened beverages** (soda, sweet tea) and **high-fructose corn syrup** — *the* leading modifiable driver. Also **fruit juice** (rapidly absorbed sugars). Target: **free sugars < ~5% of energy (~30 g/day)**.
- **Alcohol** — discouraged/avoided in prevention *and* treatment of MASLD (the liver is already fat-laden; alcohol adds direct injury).

### HIGH — limit
- **Saturated fat** — butter, palm oil, high-fat dairy, fatty/processed meats; disrupts liver metabolism and mitochondria.
- **Refined carbohydrates** — white bread/rice/pasta, pastries, sugary cereals; spike blood sugar and feed lipogenesis. *Carbohydrate quality matters more than quantity.*
- **Red & processed meat** — beef, lamb, pork, sausage, bacon; harmful associations with MASLD.
- **Ultra-processed foods** (NOVA group 4) — packaged snacks, store-bought frozen meals, cakes/cookies/ice cream, anything with hydrogenated oils and long additive lists.

### MODERATE — mind the total
- **Overall calorie density / large portions** — because **weight loss is the most evidence-based treatment**: **5% reduces liver fat, 7–10% reduces inflammation, ≥10% can improve fibrosis.** So a MASLD-aware score should gently favor lower-calorie, nutrient-dense dishes.

---

## 5. How this maps onto what we already compute

We already extract, per recipe, almost everything a MASLD score needs:

| MASLD factor | We already have it as… |
|---|---|
| Added sugar / fructose | nutrition `sugar_g`, HEI added-sugar estimate; Mediterranean "added sugar" flag; sugary-drink / syrup / dessert detection |
| Saturated fat | nutrition `sat_fat_g` |
| Fiber | nutrition `fiber_g` |
| Ultra-processed | nutrition `nova_group` (4 = ultra-processed) |
| Omega-3 fish | Mediterranean "oily fish" signature; fish food group |
| Olive oil / MUFA, legumes, whole grains, veg, nuts | Mediterranean ingredient tiers + nutrition food groups |
| Red/processed meat | Mediterranean red-meat / processed-meat penalties |
| Alcohol | Mediterranean spirits flag + wine/beer ingredients |
| Calorie density | nutrition `kcal` per serving / per 100 g |
| Coffee | ingredient detection (new, easy) |

**Takeaway:** a "Fatty-Liver Fit" score is largely a **MASLD-specific re-weighting of data we already have** — heavier penalties on sugar/fructose, alcohol, saturated fat, refined carbs, and ultra-processing; rewards for fiber, omega-3, olive oil, legumes, coffee; a nudge on calorie density. It doesn't require new nutrition science, just a new lens.

---

## 6. Sources

- [EASL–EASD–EASO Clinical Practice Guidelines on MASLD (2024), Journal of Hepatology](https://www.journal-of-hepatology.eu/article/S0168-8278(24)00329-5/fulltext)
- [AASLD 2023 Practice Guidance on NAFLD/MASLD (PDF)](https://med.emory.edu/departments/medicine/_documents/khakoo-aasld-assessment-management-of-nafld.pdf)
- [Fatty liver disease (MASLD) diet — Mayo Clinic](https://www.mayoclinic.org/diseases-conditions/fatty-liver-disease-masld/in-depth/fatty-liver-disease-masld-diet/art-20588469)
- [Practical Lifestyle Management of NAFLD for Busy Clinicians (PMC10877216)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10877216/)
- [Fructose and sugar: a major mediator of NAFLD — Journal of Hepatology (PMC5893377)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5893377/)
- [Fructose-containing sugars and NAFLD — systematic review/meta-analysis (PMC9325155)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9325155/)
- [Sugar-sweetened beverages and NAFLD/NASH risk (PMC10534429)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10534429/)
- [Mediterranean diet and NAFLD — systematic review (PMC8275052)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8275052/)
- [Coffee, fiber, and the Mediterranean diet in NAFLD — News-Medical summary of review](https://www.news-medical.net/news/20230919/Coffee-fiber-and-the-Mediterranean-diet-are-key-players-in-fighting-nonalcoholic-fatty-liver-disease.aspx)
