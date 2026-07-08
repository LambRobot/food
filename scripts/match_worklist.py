#!/usr/bin/env python3
"""Impact-ranked matching worklist — where to improve the matcher next.

Aggregates, across all in-scope recipes, the ingredient lines whose match is
missing / low-confidence / suspicious, ranked by CALORIE IMPACT (how much the
line contributes to a recipe's total), so we fix what actually moves accuracy.
"""
import os, sys, json, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nutrition_engine as E, nutrition_match as M
REPO = os.path.dirname(HERE); DATA = os.path.join(REPO, 'data')

recs = json.load(open(os.path.join(DATA, 'all_recipes.json')))['recipes']

# suspicious = a savory ingredient matched to an obviously wrong food class
SUSPECT = ['cake', 'candy', 'candies', 'buns', 'cookie', 'dessert', 'ice cream', 'frosting',
           'extender', 'wurst', 'salami', 'liver', 'giblet', 'baby food', 'infant', 'snack',
           'tea', 'palm kernel', 'skin only', 'imitation']

unmatched = defaultdict(lambda: [0, 0.0, ''])   # name -> [count, kcal, example]
lowconf = defaultdict(lambda: [0, 0.0, '', ''])  # name -> [count, kcal, match_desc, example]
suspect = defaultdict(lambda: [0, 0.0, '', ''])

for r in recs:
    if r.get('out_of_scope'):
        continue
    for line in r['ingredients']:
        if E.SKIP_LINE.match(line):
            continue
        amount, unit, name = E.parse_amount(line)
        if not name:
            continue
        key = ' '.join(M.normalize(name)) or name.lower()
        fid, food, conf = M.match(name)
        grams, gconf = E.to_grams(amount, unit, name.lower(), food)
        kcal = grams / 100.0 * food['n'].get('kcal', 0) if food else 0
        if not food:
            u = unmatched[key]; u[0] += 1; u[1] += kcal; u[2] = line.strip()[:44]
        else:
            desc = food['desc'].lower()
            if any(w in desc for w in SUSPECT):
                s = suspect[key]; s[0] += 1; s[1] += kcal; s[2] = food['desc'][:34]; s[3] = line.strip()[:36]
            elif conf < 0.6 or gconf < 0.4:
                lc = lowconf[key]; lc[0] += 1; lc[1] += kcal; lc[2] = food['desc'][:30]; lc[3] = line.strip()[:34]

def top(d, n=18):
    return sorted(d.items(), key=lambda kv: -(kv[1][1] + kv[1][0] * 20))[:n]

print('=== SUSPICIOUS MATCHES (wrong food class) — highest impact ===')
for k, v in top(suspect):
    print(f'  {v[0]:2d}x ~{v[1]:6.0f}kcal  {k[:26]:26s} -> {v[2]:34s}  e.g. "{v[3]}"')
print('\n=== UNMATCHED ingredients — highest impact ===')
for k, v in top(unmatched):
    print(f'  {v[0]:2d}x ~{v[1]:6.0f}kcal  {k[:30]:30s}  e.g. "{v[2]}"')
print('\n=== LOW-CONFIDENCE matches — highest impact ===')
for k, v in top(lowconf):
    print(f'  {v[0]:2d}x ~{v[1]:6.0f}kcal  {k[:26]:26s} -> {v[2]:30s}  e.g. "{v[3]}"')
