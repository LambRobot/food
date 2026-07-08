#!/usr/bin/env python3
"""Ground-truth calibration: compare the engine's estimates against the ORIGINAL
published nutrition scraped from each recipe's source site (~120 recipes).

Two comparisons:
  A. Serving-aligned absolute error  — our (total / source-serving-count) vs the
     source's per-serving Calories / Protein / Carb / Fat.
  B. Macro-distribution error (serving-INDEPENDENT) — % of calories from protein/
     carb/fat; tests whether we got the ingredient composition right regardless of
     any servings disagreement.

Reports the measured error band overall and split by our confidence level (to check
that "high" confidence really is more accurate), and writes data/nutrition_calibration.md.
"""
import os, re, sys, json, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nutrition_engine as E
REPO = os.path.dirname(HERE); DATA = os.path.join(REPO, 'data')

def num(pat, text):
    m = re.search(pat, text, re.I)
    return float(m.group(1)) if m else None

def parse_source_nutrition(s):
    """Extract kcal, protein, carb, fat (per source serving) from a messy string.

    Two layouts occur: "value Label" ("879 Calories, 50g Fat") and "Label value"
    ("Calories: 94kcal, Fat: 8.6g"). We try the value-before form first, then
    value-after, per field.
    """
    # Disambiguate by the colon: "Calories: 238" -> value AFTER; "879 Calories" -> value BEFORE.
    kcal = (num(r'([\d.]+)\s*kcal', s)                        # "168 kcal" (explicit unit)
            or num(r'cal(?:orie)?s?:\s*([\d.]+)', s)          # "Calories: 238.2", "Cals: 168"
            or num(r'([\d.]+)\s+calories?\b', s))             # "879 Calories" (space, value before)
    def macro(label):
        return (num(r'([\d.]+)\s*g\s+' + label, s)            # "50g Fat"
                or num(label + r's?:\s*([\d.]+)', s)          # "Fat: 8.6" (colon; handles concatenated)
                or num(label + r's?\s+([\d.]+)\s*g', s))      # "Fat 8g"
    # total fat: strip saturated/trans/poly/mono-fat mentions first so we don't grab them
    sf = re.sub(r'(saturated|trans|poly\w*|mono\w*)\s*fat:?\s*[\d.]+\s*m?g?', ' ', s, flags=re.I)
    fat = (num(r'([\d.]+)\s*g\s+fat', sf) or num(r'\bfats?:\s*([\d.]+)', sf)
           or num(r'\bfats?\s+([\d.]+)\s*g', sf))
    return {'kcal': kcal, 'protein': macro('Protein'), 'carb': macro('Carbohydrate'), 'fat': fat}

recs = {r['id']: r for r in json.load(open(os.path.join(DATA, 'all_recipes.json')))['recipes']}
nut = {r['id']: r for r in json.load(open(os.path.join(DATA, 'recipe_nutrition.json')))['recipes']}

pairs = []
for rid, r in recs.items():
    if not r.get('nutrition') or r.get('out_of_scope'):
        continue
    src = parse_source_nutrition(r['nutrition'])
    if not src['kcal']:
        continue
    n = nut[rid]
    src_serv = E.parse_servings(r.get('servings'))    # the source's own serving count
    pairs.append({'id': rid, 'name': r['name'], 'src': src, 'our': n['per_serving'],
                  'our_total': n['total_kcal'], 'src_serv': src_serv,
                  'conf': n['coverage']['confidence']})

def pct_err(our, src):
    return abs(our - src) / src * 100 if src else None

# ---- A. serving-aligned absolute error ----
def macro_dist(kcal, p, c, f):
    if not kcal or kcal <= 0: return None
    return {'p': p * 4 / kcal * 100, 'c': c * 4 / kcal * 100, 'f': f * 9 / kcal * 100}

rows = []
for pr in pairs:
    src, our = pr['src'], pr['our']
    aligned_kcal = pr['our_total'] / pr['src_serv'] if pr['src_serv'] else None
    e = {'id': pr['id'], 'name': pr['name'], 'conf': pr['conf'],
         'kcal_err': pct_err(aligned_kcal, src['kcal']) if aligned_kcal else None}
    if all(src.get(k) is not None for k in ('protein', 'carb', 'fat')):
        md_src = macro_dist(src['kcal'], src['protein'], src['carb'], src['fat'])
        md_our = macro_dist(our['kcal'], our['protein_g'], our['carb_g'], our['fat_g'])
        if md_src and md_our:
            e['macro_err'] = (abs(md_src['p'] - md_our['p']) + abs(md_src['c'] - md_our['c'])
                              + abs(md_src['f'] - md_our['f'])) / 3      # avg %-point error
    rows.append(e)

def med(vals):
    vals = [v for v in vals if v is not None]
    return round(st.median(vals), 1) if vals else None

kcal_errs = [r['kcal_err'] for r in rows if r.get('kcal_err') is not None]
macro_errs = [r['macro_err'] for r in rows if r.get('macro_err') is not None]

L = ['# Nutrition Engine — Ground-Truth Calibration\n',
     f'Compared the engine against the **original published nutrition** scraped from each '
     f"recipe's source, for **{len(pairs)}** in-scope recipes that carry it.\n",
     '## A. Serving-aligned energy error (our total ÷ source servings vs. source kcal/serving)\n',
     f'- median absolute error: **{med(kcal_errs)}%**  ·  n={len(kcal_errs)}',
     f'- within 15%: {round(100*sum(1 for e in kcal_errs if e<=15)/len(kcal_errs))}%  ·  '
     f'within 25%: {round(100*sum(1 for e in kcal_errs if e<=25)/len(kcal_errs))}%  ·  '
     f'within 40%: {round(100*sum(1 for e in kcal_errs if e<=40)/len(kcal_errs))}%\n',
     '## B. Macro-distribution error (serving-independent; avg %-point diff across P/C/F)\n',
     f'- median: **{med(macro_errs)} percentage points**  ·  n={len(macro_errs)}\n',
     '## Does confidence track accuracy?\n',
     '| Our confidence | n | median energy error | median macro-dist error |',
     '|---|--:|--:|--:|']
for c in ('high', 'medium', 'low'):
    ke = med([r['kcal_err'] for r in rows if r['conf'] == c and r.get('kcal_err') is not None])
    me = med([r['macro_err'] for r in rows if r['conf'] == c and r.get('macro_err') is not None])
    cnt = sum(1 for r in rows if r['conf'] == c)
    L.append(f'| {c} | {cnt} | {ke}% | {me} pp |')

worst = sorted([r for r in rows if r.get('kcal_err') is not None], key=lambda x: -x['kcal_err'])[:12]
L += ['', '## Worst energy mismatches (candidates for the next fix)\n',
      '| Recipe | conf | energy error |', '|---|---|--:|']
for r in worst:
    L.append(f"| {r['name'][:44]} | {r['conf']} | {r['kcal_err']:.0f}% |")

open(os.path.join(DATA, 'nutrition_calibration.md'), 'w', encoding='utf-8').write('\n'.join(L))

print(f'Calibrated on {len(pairs)} recipes with source nutrition')
print(f'A. serving-aligned energy: median abs error {med(kcal_errs)}%  '
      f'(within 25%: {round(100*sum(1 for e in kcal_errs if e<=25)/len(kcal_errs))}%)')
print(f'B. macro-distribution:     median {med(macro_errs)} percentage points')
print('\nBy confidence (energy error):')
for c in ('high', 'medium', 'low'):
    ke = med([r['kcal_err'] for r in rows if r['conf'] == c and r.get('kcal_err') is not None])
    cnt = sum(1 for r in rows if r['conf'] == c and r.get('kcal_err') is not None)
    print(f'  {c:6s} n={cnt:3d}  median energy error {ke}%')
