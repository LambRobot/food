# Nutrition Engine — Ground-Truth Calibration

Compared the engine against the **original published nutrition** scraped from each recipe's source, for **96** in-scope recipes that carry it.

## A. Serving-aligned energy error (our total ÷ source servings vs. source kcal/serving)

- median absolute error: **24.0%**  ·  n=92
- within 15%: 37%  ·  within 25%: 52%  ·  within 40%: 64%

## B. Macro-distribution error (serving-independent; avg %-point diff across P/C/F)

- median: **8.0 percentage points**  ·  n=77

## Does confidence track accuracy?

| Our confidence | n | median energy error | median macro-dist error |
|---|--:|--:|--:|
| high | 74 | 22.1% | 7.7 pp |
| medium | 20 | 41.1% | 14.4 pp |
| low | 2 | 63.4% | None pp |

## Worst energy mismatches (candidates for the next fix)

| Recipe | conf | energy error |
|---|---|--:|
| Million Dollar Deviled Eggs | high | 2005% |
| Chili Lime Chicken Sweet Potato Skillet | high | 1194% |
| One Pot Chicken and Rice with Coconut Milk | high | 432% |
| Old-Time Custard Ice Cream | high | 282% |
| The BEST Chicken Enchilada | high | 163% |
| Red Velvet Cupcakes | high | 140% |
| Soft-Boiled Eggs for Ramen (modified By Tom) | medium | 130% |
| Roast Pork Shoulder Ragù in Bianco with Past | high | 124% |
| Gyudon (Japanese Simmered Beef and Rice Bowl | high | 110% |
| Coconut Almond Chia Seed Pudding | high | 100% |
| Red Velvet Cake | high | 95% |
| Seeduction Bread (Copykat - Whole Foods Reci | high | 92% |