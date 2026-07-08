#!/usr/bin/env python3
"""Regression test harness for the whole pipeline (Tier-1 reliability net).

Run after any engine change:  python3 scripts/test_engine.py
Exits non-zero if any check fails, so bugs can't silently regress.

Checks:
  1. Cross-file integrity — all data files share the same recipe ids.
  2. Per-recipe invariants — no negative/NaN nutrients, calories reconcile with
     macros, servings >=1, coverage present, etc.
  3. Golden anchors — ~24 hand-verified recipes must stay within tolerance.
  4. Anomaly gate — no in-scope, high-confidence recipe with implausible values.
"""
import os, json, sys, math

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'data')
def load(f): return json.load(open(os.path.join(DATA, f)))['recipes']

fails, warns = [], []
def check(cond, msg):
    if not cond: fails.append(msg)

# ---- 1. cross-file id integrity ----
files = ['all_recipes.json', 'recipe_mediterranean_scores.json', 'recipe_improvements.json',
         'recipe_nutrition.json', 'index.json']
idsets = {f: {r['id'] for r in load(f)} for f in files}
base = idsets['all_recipes.json']
for f, s in idsets.items():
    check(s == base, f'{f}: id set differs from all_recipes ({len(s)} vs {len(base)})')

nut = {r['id']: r for r in load('recipe_nutrition.json')}

# ---- 2. per-recipe invariants ----
for rid, r in nut.items():
    p = r['per_serving']
    tag = f'nutrition[{rid}]'
    check(r['servings'] >= 1, f'{tag}: servings < 1')
    check(r['total_kcal'] >= 0, f'{tag}: negative total_kcal')
    for k, v in p.items():
        check(isinstance(v, (int, float)) and not math.isnan(v) and v >= 0, f'{tag}: bad {k}={v}')
    check(r['coverage']['confidence'] in ('high', 'medium', 'low'), f'{tag}: bad confidence')
    # calories reconcile with macros (4/4/9) within 30% for high-confidence non-trivial dishes
    if r['coverage']['confidence'] == 'high' and p['kcal'] > 120:
        macro_kcal = p['protein_g'] * 4 + p['carb_g'] * 4 + p['fat_g'] * 9
        if macro_kcal > 0:
            ratio = macro_kcal / p['kcal']
            if not (0.6 <= ratio <= 1.5):
                warns.append(f'{tag}: macro kcal {macro_kcal:.0f} vs stated {p["kcal"]} (ratio {ratio:.2f})')
    # per-serving * servings ~= total
    check(abs(p['kcal'] * r['servings'] - r['total_kcal']) <= max(30, 0.06 * r['total_kcal']),
          f'{tag}: per_serving*servings != total_kcal')

# ---- 3. golden anchors ----
golden = json.load(open(os.path.join(REPO, 'tests', 'golden.json')))['recipes']
KTOL = 0.30
for rid, g in golden.items():
    if rid not in nut:
        fails.append(f'golden[{rid}]: missing from nutrition output'); continue
    r = nut[rid]; p = r['per_serving']
    def within(cur, exp, tol=KTOL, floor=5):
        return abs(cur - exp) <= max(floor, tol * abs(exp))
    check(within(p['kcal'], g['kcal_serv']), f'golden[{rid}] kcal {p["kcal"]} vs {g["kcal_serv"]}')
    check(within(p['protein_g'], g['protein_g'], floor=4), f'golden[{rid}] protein {p["protein_g"]} vs {g["protein_g"]}')
    check(within(p['fat_g'], g['fat_g'], floor=5), f'golden[{rid}] fat {p["fat_g"]} vs {g["fat_g"]}')
    check(r['dish_type'] == g['dish_type'], f'golden[{rid}] dish_type {r["dish_type"]} vs {g["dish_type"]}')
    grades = 'ABCDE'
    check(abs(grades.index(r['health_scores']['nutri_score']['grade']) - grades.index(g['nutri_score'])) <= 1,
          f'golden[{rid}] nutri {r["health_scores"]["nutri_score"]["grade"]} vs {g["nutri_score"]}')

# ---- 4. anomaly gate (in-scope, high-confidence) ----
# FAIL only on physically-implausible values; WARN on suspicious-but-possible
# (genuinely rich dishes exist). Golden anchors + invariants catch per-recipe regressions.
for rid, r in nut.items():
    if r.get('out_of_scope') or r['coverage']['confidence'] != 'high':
        continue
    p = r['per_serving']; dt = r['dish_type']; tag = f'anomaly[{rid} "{r["name"][:28]}"]'
    def gate(val, warn_hi, fail_hi, unit):
        if val > fail_hi: fails.append(f'{tag}: {unit}={val} (>{fail_hi} impossible)')
        elif val > warn_hi: warns.append(f'{tag}: {unit}={val} (rich — review)')
    if dt in ('main', 'soup/stew') and p['kcal'] < 60:
        fails.append(f'{tag}: {dt} only {p["kcal"]} kcal/serv')
    gate(p['kcal'], 1200, 2000, 'kcal')
    gate(p['fiber_g'], 25, 35, 'fiber_g')
    gate(p['protein_g'], 110, 150, 'protein_g')
    gate(p['fat_g'], 130, 170, 'fat_g')
    gate(p['sodium_mg'], 4000, 6500, 'sodium_mg')

# ---- report ----
print(f'Checked {len(nut)} recipes | {len(golden)} golden anchors')
if warns:
    print(f'\n{len(warns)} warnings:')
    for w in warns[:20]: print('  ⚠︎ ', w)
if fails:
    print(f'\n❌ {len(fails)} FAILURES:')
    for f in fails[:40]: print('  ✗', f)
    sys.exit(1)
print('\n✅ ALL CHECKS PASSED')
