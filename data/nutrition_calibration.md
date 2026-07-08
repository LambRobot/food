# Nutrition Engine — Ground-Truth Calibration

Compared the engine against the **original published nutrition** scraped from each recipe's source, for **96** in-scope recipes that carry it.

## A. Serving-aligned energy error (our total ÷ source servings vs. source kcal/serving)

- median absolute error: **21.9%**  ·  n=92
- within 15%: 33%  ·  within 25%: 55%  ·  within 40%: 67%

## B. Macro-distribution error (serving-independent; avg %-point diff across P/C/F)

- median: **8.3 percentage points**  ·  n=77

## Does confidence track accuracy?

| Our confidence | n | median energy error | median macro-dist error |
|---|--:|--:|--:|
| high | 79 | 21.2% | 7.6 pp |
| medium | 15 | 23.3% | 8.9 pp |
| low | 2 | 79.3% | 10.8 pp |

## Worst energy mismatches (candidates for the next fix)

| Recipe | conf | energy error |
|---|---|--:|
| Million Dollar Deviled Eggs | high | 2011% |
| Chili Lime Chicken Sweet Potato Skillet | high | 1106% |
| Old-Time Custard Ice Cream | high | 282% |
| One Pot Chicken and Rice with Coconut Milk | high | 278% |
| The BEST Chicken Enchilada | high | 163% |
| Red Velvet Cupcakes | high | 140% |
| Soft-Boiled Eggs for Ramen (modified By Tom) | medium | 130% |
| Gyudon (Japanese Simmered Beef and Rice Bowl | high | 110% |
| Coconut Almond Chia Seed Pudding | high | 100% |
| Red Velvet Cake | high | 95% |
| Seeduction Bread (Copykat - Whole Foods Reci | high | 92% |
| Nappage Chocolat | low | 86% |