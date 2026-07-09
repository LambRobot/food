#!/usr/bin/env python3
"""Fatty-Liver Fit score — a MASLD/NAFLD-specific health lens (clinical/strict).

A separate 6th dimension. Re-weights data we already compute (nutrition macros +
NOVA processing + Mediterranean ingredient groups) per the 2024 EASL/AASLD dietary
guidance (see fatty_liver_diet_wiki.md): added sugar/fructose and alcohol are the
heaviest penalties, then saturated fat / refined carbs / red-&-processed meat /
ultra-processing; rewards for omega-3 fish, fibre, olive oil, legumes, whole
grains, vegetables, nuts, and coffee. Educational, NOT medical advice.

Output: data/recipe_fatty_liver.{json,md}. Join on `id`.
"""
import os, re, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'data')

recs = {r['id']: r for r in json.load(open(os.path.join(DATA, 'all_recipes.json')))['recipes']}
nut = {r['id']: r for r in json.load(open(os.path.join(DATA, 'recipe_nutrition.json')))['recipes']}
med = {r['id']: r for r in json.load(open(os.path.join(DATA, 'recipe_mediterranean_scores.json')))['recipes']}

def has(text, *words):
    return any(re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text) for w in words)

# ingredient-text signals not already captured elsewhere
SSB = ['soda', 'cola', 'soft drink', 'sprite', 'lemonade', 'sweet tea', 'kool-aid', 'gatorade', 'soda pop']
JUICE = ['orange juice', 'apple juice', 'fruit juice', 'grape juice', 'cranberry juice', 'juice concentrate']
HFCS = ['high-fructose', 'high fructose', 'corn syrup', 'glucose-fructose', 'agave']
SYRUP = ['maple syrup', 'golden syrup', 'molasses', 'honey', 'sugar', 'brown sugar', 'condensed milk']
COFFEE = ['coffee', 'espresso', 'cold brew']
WINE_BEER = ['wine', 'beer', 'sherry', 'marsala', 'sake', 'vermouth', 'port', 'cider']
SPIRITS = ['bourbon', 'whiskey', 'whisky', 'rum', 'vodka', 'tequila', 'brandy', 'cognac', 'liqueur',
           'kirsch', 'cointreau', 'grand marnier', 'triple sec', 'amaretto', 'schnapps']

def alcohol_kind(ingredients):
    """(has_spirits, has_wine_beer) — skips vinegar/extract lines (not drinkable alcohol)."""
    spirits = wineb = False
    for line in ingredients:
        l = line.lower()
        if 'vinegar' in l or 'extract' in l:      # "red wine vinegar", "vanilla extract"
            continue
        if has(l, *SPIRITS):
            spirits = True
        elif has(l, *WINE_BEER):
            wineb = True
    return spirits, wineb

def score_recipe(rid):
    r = recs[rid]; n = nut[rid]; m = med[rid]
    p = n['per_serving']
    posg = m['breakdown']['positive_by_group']
    negg = m['breakdown']['negative_by_group']
    text = ' '.join(r['ingredients']).lower()
    is_dessert = n.get('dish_type') == 'dessert'

    score = 50.0
    good, risk = [], []

    # ---------- SEVERE penalties ----------
    # Added sugar / fructose — the #1 MASLD driver. Approx added sugar = total - intrinsic
    # (fruit/veg/dairy). Use the Mediterranean "added sugar" flag to confirm it's added.
    sugar = p['sugar_g']
    added_flag = 'ADDED_SUGAR' in negg or has(text, *SSB) or has(text, *JUICE) or has(text, *HFCS) or is_dessert
    if added_flag:
        sugar_pen = min(34, max(0, sugar - 4) * 3.2)          # strict slope, per serving
        if has(text, *SSB) or has(text, *HFCS):
            sugar_pen += 16; risk.append('🔴 sugary drink / HFCS — the top liver-fat driver')
        elif has(text, *JUICE):
            sugar_pen += 8; risk.append('🔴 fruit juice — rapidly absorbed fructose')
        if sugar_pen:
            score -= sugar_pen
            if sugar > 12 and 'sugary drink' not in ' '.join(risk):
                risk.append(f'🔴 high added sugar (~{sugar:.0f} g/serving)')

    # Alcohol — discouraged in MASLD. Spirits/liqueur penalised hardest; wine/beer used
    # in cooking (much evaporates) somewhat less, but still flagged (clinical/strict).
    spirits, wineb = alcohol_kind(r['ingredients'])
    if spirits:
        score -= 22; risk.append('🔴 contains spirits/liqueur — alcohol discouraged for fatty liver')
    elif wineb:
        score -= 11; risk.append('🔴 cooking wine/beer — alcohol discouraged for fatty liver')

    # ---------- HIGH penalties ----------
    sat = p['sat_fat_g']
    if sat > 5:
        score -= min(22, (sat - 5) * 2.0); risk.append(f'🟠 saturated fat (~{sat:.0f} g/serving)')
    if 'REFINED_GRAIN' in negg:
        score -= 9; risk.append('🟠 refined carbs (spike blood sugar → liver fat)')
    if 'PROCESSED_MEAT' in negg:
        score -= 13; risk.append('🟠 processed meat')
    elif 'RED_MEAT' in negg:
        score -= 8; risk.append('🟠 red meat')
    if n['health_scores']['nova_group'] == 4:
        score -= 10; risk.append('🟠 ultra-processed (NOVA 4)')
    if 'TROPICAL' in negg:
        score -= 6; risk.append('🟡 coconut/palm (saturated) fat')

    # ---------- MODERATE: calorie density (weight loss is the key treatment) ----------
    if p['kcal'] > 650:
        score -= min(10, (p['kcal'] - 650) / 100 * 2.0); risk.append(f'🟡 calorie-dense (~{p["kcal"]:.0f} kcal/serving)')

    # ---------- REWARDS ----------
    if 'FISH' in posg:
        # only oily fish is the omega-3 win; approximate via the med good list
        oily = any(w in ' '.join(g['ingredient'] for g in m['good_ingredients'])
                   for w in ('salmon', 'sardine', 'mackerel', 'anchov', 'tuna', 'trout', 'herring'))
        if oily:
            score += 12; good.append('✅ omega-3 oily fish (protects against liver fat)')
        else:
            score += 5; good.append('✓ fish/seafood')
    if 'OLIVE_OIL' in posg:
        score += 6; good.append('✅ olive oil')
    fiber = p['fiber_g']
    if fiber > 2:
        score += min(15, fiber * 1.4); good.append(f'✅ fibre (~{fiber:.0f} g — improves insulin sensitivity)')
    if 'LEGUME' in posg:
        score += 8; good.append('✅ legumes')
    if 'WHOLEGRAIN' in posg:
        score += 6; good.append('✅ whole grains')
    if 'VEG' in posg:
        score += min(12, posg['VEG'] * 0.9); good.append('✅ plenty of vegetables')
    if 'NUTS' in posg:
        score += 4; good.append('✓ nuts/seeds')
    if has(text, *COFFEE):
        score += 6; good.append('☕ coffee (linked to less liver fibrosis)')

    score = max(0, min(100, round(score)))
    grade = 'A' if score >= 80 else 'B' if score >= 65 else 'C' if score >= 50 else 'D' if score >= 35 else 'F'
    verdict = {
        'A': 'Excellent for a fatty-liver diet — eat freely.',
        'B': 'Liver-friendly — a good regular choice.',
        'C': 'Okay in moderation / with tweaks.',
        'D': 'Not ideal for fatty liver — occasional only.',
        'F': 'Avoid on a fatty-liver diet — rare exception at most.',
    }[grade]
    return {
        'id': rid, 'name': r['name'], 'score': score, 'grade': grade,
        'verdict': verdict,
        'good_factors': good, 'risk_factors': risk,
        'nutrition_confidence': n['coverage']['confidence'],  # inherits nutrition reliability
    }

out = [score_recipe(rid) for rid in recs]
out.sort(key=lambda x: (-x['score'], x['name'].lower()))

with open(os.path.join(DATA, 'recipe_fatty_liver.json'), 'w', encoding='utf-8') as fh:
    json.dump({'recipe_count': len(out),
               'reference': 'fatty_liver_diet_wiki.md',
               'disclaimer': 'Educational, evidence-based food scoring for MASLD/NAFLD — NOT medical advice. Consult a hepatologist/dietitian.',
               'strictness': 'clinical',
               'recipes': out}, fh, ensure_ascii=False, indent=2)

# markdown
SEV = {'A': '🟢', 'B': '🟢', 'C': '🟡', 'D': '🟠', 'F': '🔴'}
L = ['# Fatty-Liver Fit — Recipe Scores (MASLD/NAFLD)\n',
     '> **Educational, evidence-based food scoring — NOT medical advice.** Based on '
     '`fatty_liver_diet_wiki.md` (2024 EASL/AASLD guidance). Clinical/strict weighting: '
     'added sugar/fructose and alcohol are penalised hardest, then saturated fat, refined '
     'carbs, red/processed meat, and ultra-processing; rewards for omega-3 fish, fibre, olive '
     'oil, legumes, whole grains, vegetables and coffee. Consult a hepatologist/dietitian.\n']
from collections import Counter
gc = Counter(r['grade'] for r in out)
L.append('**' + ' · '.join(f'{g}: {gc.get(g,0)}' for g in 'ABCDF') + f'** · avg {round(sum(r["score"] for r in out)/len(out))}/100\n')
L.append('| Recipe | Score | Grade | Key factors |')
L.append('|---|--:|:--:|---|')
for r in out:
    factors = '; '.join((r['good_factors'][:2] + r['risk_factors'][:2]))[:90]
    L.append(f"| {r['name']} | {r['score']} | {SEV[r['grade']]} {r['grade']} | {factors} |")
open(os.path.join(DATA, 'recipe_fatty_liver.md'), 'w', encoding='utf-8').write('\n'.join(L))

print(f'Scored {len(out)} recipes for fatty-liver fit')
print('Grades:', dict(sorted(gc.items())), '| avg', round(sum(r['score'] for r in out)/len(out)))
print('\nTop 8 (liver-friendly):')
for r in out[:8]:
    print(f"  {r['score']:3d} {r['grade']}  {r['name'][:44]}")
print('Bottom 6:')
for r in out[-6:]:
    print(f"  {r['score']:3d} {r['grade']}  {r['name'][:44]}")
