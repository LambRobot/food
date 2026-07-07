#!/usr/bin/env python3
"""Build a compact offline nutrition reference from USDA FoodData Central bulk CSVs.

Input : USDA SR Legacy + Foundation Foods CSV downloads (see scripts/fetch_usda.sh),
        located under $USDA_DIR (default: data/usda_src/, git-ignored — it's large and
        reconstructible). We extract only the ~25 nutrients we need + household portions.
Output: data/usda_reference.json — { fdc_id: {desc, type, cat, n:{nutrient:per100g}, portions:[...]} }

Runtime nutrition engine reads only this compact file, so it stays offline & deterministic.
"""
import os, csv, json, glob, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USDA_DIR = os.environ.get('USDA_DIR', os.path.join(REPO, 'data', 'usda_src'))
OUT = os.path.join(REPO, 'data', 'usda_reference.json')
csv.field_size_limit(1 << 24)

# USDA nutrient_id -> our short key. (Energy handled specially: 1008 preferred.)
NUTRIENTS = {
    1003: 'protein', 1004: 'fat', 1005: 'carb', 1079: 'fiber', 2000: 'sugar', 1063: 'sugar',
    1258: 'sat_fat', 1257: 'trans_fat', 1253: 'cholesterol', 1093: 'sodium',
    1087: 'calcium', 1089: 'iron', 1090: 'magnesium', 1091: 'phosphorus', 1092: 'potassium',
    1095: 'zinc', 1106: 'vit_a_rae', 1162: 'vit_c', 1114: 'vit_d', 1109: 'vit_e', 1185: 'vit_k',
    1177: 'folate', 1165: 'thiamin', 1166: 'riboflavin', 1167: 'niacin', 1175: 'vit_b6', 1178: 'vit_b12',
}
ENERGY_IDS = [1008, 2048, 2047]   # preference order (kcal)
KEEP_TYPES = {'sr_legacy_food', 'foundation_food', 'sample_food'}

def find_dirs():
    dirs = [d for d in glob.glob(os.path.join(USDA_DIR, '*')) if os.path.isdir(d)]
    dirs = [d for d in dirs if os.path.exists(os.path.join(d, 'food.csv'))]
    if not dirs:
        sys.exit(f'No USDA CSV folders under {USDA_DIR}. Run scripts/fetch_usda.sh first.')
    return dirs

def reader(path):
    with open(path, encoding='utf-8', newline='') as fh:
        for row in csv.DictReader(fh):
            yield row

foods = {}      # fdc_id -> {desc,type,cat}
measure = {}    # measure_unit_id -> name
per100 = {}     # fdc_id -> {key: amount}
energy = {}     # fdc_id -> {energy_id: amount}
portions = {}   # fdc_id -> [ {amount, unit, modifier, grams} ]

for d in find_dirs():
    # measure units
    mp = os.path.join(d, 'measure_unit.csv')
    if os.path.exists(mp):
        for r in reader(mp):
            measure[r['id']] = r['name']
    # foods
    for r in reader(os.path.join(d, 'food.csv')):
        if r['data_type'] in KEEP_TYPES:
            foods[r['fdc_id']] = {'desc': r['description'], 'type': r['data_type'],
                                  'cat': r.get('food_category_id') or ''}
    # nutrients
    for r in reader(os.path.join(d, 'food_nutrient.csv')):
        fid = r['fdc_id']
        if fid not in foods:
            continue
        try:
            nid = int(r['nutrient_id']); amt = float(r['amount'] or 0)
        except ValueError:
            continue
        if nid in ENERGY_IDS:
            energy.setdefault(fid, {})[nid] = amt
        elif nid in NUTRIENTS:
            key = NUTRIENTS[nid]
            # 'sugar' maps from 2000 or 1063; keep the first non-zero we see
            if key not in per100.get(fid, {}):
                per100.setdefault(fid, {})[key] = amt
    # portions
    pp = os.path.join(d, 'food_portion.csv')
    if os.path.exists(pp):
        for r in reader(pp):
            fid = r['fdc_id']
            if fid not in foods:
                continue
            try:
                grams = float(r['gram_weight'] or 0)
            except ValueError:
                continue
            if grams <= 0:
                continue
            unit = measure.get(r.get('measure_unit_id'), '')
            if unit in ('9999', 'undetermined'):
                unit = ''
            portions.setdefault(fid, []).append({
                'amount': float(r['amount'] or 1), 'unit': unit,
                'modifier': (r.get('modifier') or r.get('portion_description') or '').strip(),
                'grams': grams,
            })

# assemble
ref = {}
for fid, meta in foods.items():
    n = dict(per100.get(fid, {}))
    e = energy.get(fid, {})
    kcal = next((e[i] for i in ENERGY_IDS if i in e), None)
    if kcal is None and not n:
        continue           # no usable data
    if kcal is not None:
        n['kcal'] = kcal
    ref[fid] = {'desc': meta['desc'], 'type': meta['type'], 'cat': meta['cat'],
                'n': {k: round(v, 4) for k, v in n.items()},
                'portions': portions.get(fid, [])}

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump({'food_count': len(ref), 'nutrient_keys': sorted(set(NUTRIENTS.values()) | {'kcal'}),
               'source': 'USDA FoodData Central (SR Legacy 2018-04 + Foundation Foods 2025-12)',
               'foods': ref}, fh, ensure_ascii=False, separators=(',', ':'))

sz = os.path.getsize(OUT) / 1e6
print(f'Wrote {len(ref)} foods -> {OUT} ({sz:.1f} MB)')
print('with energy:', sum(1 for f in ref.values() if 'kcal' in f['n']),
      '| with portions:', sum(1 for f in ref.values() if f['portions']))
