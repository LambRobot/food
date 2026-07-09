#!/usr/bin/env python3
"""Bundle the 6 data dimensions into one compact file for the web UI.

Writes web/data.js (a JS global, so web/index.html works by double-click via file://
AND when hosted on GitHub Pages). Merges everything the UI needs per recipe, joined
on `id`.
"""
import os, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'data')
WEB = os.path.join(REPO, 'web')
os.makedirs(WEB, exist_ok=True)

def load(f):
    return {r['id']: r for r in json.load(open(os.path.join(DATA, f)))['recipes']}

recs = load('all_recipes.json')
idx = load('index.json')
med = load('recipe_mediterranean_scores.json')
nut = load('recipe_nutrition.json')
liver = load('recipe_fatty_liver.json')
imp = load('recipe_improvements.json')

out = []
for rid, r in recs.items():
    ix = idx.get(rid, {})
    m = med.get(rid, {})
    n = nut.get(rid, {})
    lv = liver.get(rid, {})
    im = imp.get(rid, {})
    p = n.get('per_serving', {})
    out.append({
        'id': rid,
        'name': r['name'],
        'cuisine': ix.get('cuisine'),
        'cuisine_guess': ix.get('cuisine_source') != 'category',
        'dish_type': ix.get('dish_type') or n.get('dish_type'),
        'categories': r.get('categories') or [],
        'servings': n.get('servings'),
        'source': r.get('source'), 'source_url': r.get('source_url'),
        'flags': ix.get('flags', {}),
        'ingredients': r.get('ingredients') or [],
        'directions': r.get('directions') or [],
        'notes': r.get('notes'),
        # Mediterranean
        'med_score': m.get('score'), 'med_grade': m.get('grade'), 'med_comment': m.get('comment'),
        'med_good': [g['ingredient'] for g in m.get('good_ingredients', [])],
        'med_bad': [{'i': b['ingredient'], 's': b['severity']} for b in m.get('bad_ingredients', [])],
        'med_suggestions': m.get('suggestions', []),
        # Nutrition
        'kcal': p.get('kcal'), 'total_kcal': n.get('total_kcal'),
        'kcal_range': n.get('kcal_range'), 'uncertainty_pct': n.get('uncertainty_pct'),
        'protein_g': p.get('protein_g'), 'carb_g': p.get('carb_g'), 'fiber_g': p.get('fiber_g'),
        'sugar_g': p.get('sugar_g'), 'fat_g': p.get('fat_g'), 'sat_fat_g': p.get('sat_fat_g'),
        'sodium_mg': p.get('sodium_mg'),
        'nutri': (n.get('health_scores') or {}).get('nutri_score', {}).get('grade'),
        'nrf': (n.get('health_scores') or {}).get('nrf9_3'),
        'nova': (n.get('health_scores') or {}).get('nova_group'),
        'hei': ((n.get('health_scores') or {}).get('hei_2020') or {}).get('total') if (n.get('health_scores') or {}).get('hei_2020') else None,
        'cooking_method': n.get('cooking_method'),
        'nut_confidence': (n.get('coverage') or {}).get('confidence'),
        'nut_unmatched': (n.get('coverage') or {}).get('unmatched', []),
        # Fatty liver
        'liver_score': lv.get('score'), 'liver_grade': lv.get('grade'), 'liver_verdict': lv.get('verdict'),
        'liver_good': lv.get('good_factors', []), 'liver_risk': lv.get('risk_factors', []),
        # Improvement
        'imp_score': im.get('improved_score'), 'imp_grade': im.get('improved_grade'),
        'imp_delta': im.get('delta'), 'imp_swaps': im.get('swaps', []),
        'imp_changes': im.get('changed_lines', []),
    })

out.sort(key=lambda x: x['name'].lower())
payload = {'count': len(out), 'recipes': out}
with open(os.path.join(WEB, 'data.js'), 'w', encoding='utf-8') as fh:
    fh.write('window.RECIPE_DATA = ')
    json.dump(payload, fh, ensure_ascii=False, separators=(',', ':'))
    fh.write(';\n')

sz = os.path.getsize(os.path.join(WEB, 'data.js')) / 1e6
print(f'Wrote web/data.js — {len(out)} recipes ({sz:.1f} MB)')
