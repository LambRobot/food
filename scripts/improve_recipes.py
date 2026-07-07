#!/usr/bin/env python3
"""Generate an "improved" (more Mediterranean) version of every recipe.

For each recipe we detect the *swappable* penalties (bad ingredients/methods that
can be substituted without changing the dish's identity), compute how much each
single swap would help by actually re-scoring the modified recipe, then greedily
apply the top up-to-3 swaps that genuinely raise the score. Red meat is never
"swapped" (it defines the dish) and we never add olive oil from nothing — we only
switch an existing bad fat/oil to olive oil or drop/reduce a bad ingredient.

Outputs: data/recipe_improvements.md and data/recipe_improvements.json
"""
import os, sys, re, json, copy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_recipes as S

REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, 'data')

MAX_SWAPS = 3
# Groups we will try to fix, and the human description of the swap.
SWAP_LABEL = {
    'PROCESSED_MEAT': 'Drop the cured/processed meat (or use a tiny amount as a garnish)',
    'BUTTER_CREAM':   'Butter/cream → extra-virgin olive oil or plain Greek yogurt',
    'FRIED':          'Deep-fry → roast or pan-sear in olive oil',
    'TROPICAL':       'Coconut/palm fat → olive oil (or use light coconut milk sparingly)',
    'REFINED_GRAIN':  'Refined grain → whole grain (brown rice / whole-wheat / bulgur)',
    'CHEESE_HEAVY':   'Use about half the cheese — as an accent, not the base',
    'ADDED_SUGAR':    'Cut the added sugar (a little honey if needed)',
    'SODIUM':         'High-sodium sauce → reduced-sodium/low amount, herbs & lemon',
    'MAYO':           'Mayonnaise → plain Greek yogurt / olive-oil dressing',
    'NEUTRAL_OIL':    'Neutral oil (canola/vegetable) → extra-virgin olive oil',
    'WHITE_POTATO':   'White potato → sweet potato or a whole grain',
}
# never-swappable: RED_MEAT (dish identity), SPIRITS
SWAPPABLE = set(SWAP_LABEL)

# ---- ingredient-line substitutions per group (specific enough to run globally) ----
def _sub_refined(line):
    l = line
    l = re.sub(r'\b(?:white |jasmine |basmati |arborio |sushi |long[- ]grain )*rice\b'
               r'(?!\s*(?:vinegar|wine|paper|noodle|flour))', 'brown rice', l, flags=re.I)
    l = re.sub(r'\b(all[- ]purpose|white|plain|bread|cake|farine|mehl)\s*flour\b', 'whole-wheat flour', l, flags=re.I)
    l = re.sub(r'\bflour\b(?<!wheat flour)', 'whole-wheat flour', l, flags=re.I) if re.search(
        r'\bflour\b', l, re.I) and not re.search(r'(almond|coconut|rice|chickpea|corn|oat|whole)', l, re.I) else l
    l = re.sub(r'\b(spaghetti|penne|fettuccine|linguine|macaroni|rigatoni|fusilli|ziti|lasagne|lasagna|'
               r'tagliatelle|orzo|pasta|noodles?)\b', r'whole-wheat \g<0>', l, flags=re.I)
    l = re.sub(r'\bcouscous\b', 'whole-wheat couscous', l, flags=re.I)
    l = re.sub(r'\b(white bread|baguette|bread|pita|naan|tortillas?|buns?|rolls?|brioche)\b',
               r'whole-grain \g<0>', l, flags=re.I)
    l = l.replace('whole-wheat whole-wheat', 'whole-wheat').replace('whole-grain whole-grain', 'whole-grain')
    return l

def _sub_butter(line):
    l = line
    l = re.sub(r'\bhalf[- ]and[- ]half\b', 'whole milk', l, flags=re.I)
    l = re.sub(r'\bsour cream\b', 'plain Greek yogurt', l, flags=re.I)
    l = re.sub(r'\bcr[eè]me\s+fra[iî]che\b', 'plain Greek yogurt', l, flags=re.I)
    l = re.sub(r'\b(?:heavy|double|whipping|heavy whipping)\s+cream\b', 'plain Greek yogurt', l, flags=re.I)
    l = re.sub(r'\bcream\b(?!\s+of\s+tartar)', 'plain Greek yogurt', l, flags=re.I)
    l = re.sub(r'\b(cr[eè]me|sahne)\b', 'plain Greek yogurt', l, flags=re.I)
    if not re.search(r'(?:pea|al|cocoa|apple)\w*\s*butter|nut butter', l, re.I):
        l = re.sub(r'\bbutter\b', 'extra-virgin olive oil', l, flags=re.I)
    l = re.sub(r'\bbeurre\b', 'extra-virgin olive oil', l, flags=re.I)
    l = re.sub(r'\b(ghee|lard|margarine|shortening|tallow|suet|crisco)\b', 'extra-virgin olive oil', l, flags=re.I)
    l = re.sub(r'\b(duck fat|drippings)\b', 'extra-virgin olive oil', l, flags=re.I)
    return l

def _sub_neutral(line):
    return re.sub(r'\b(vegetable|canola|sunflower|corn|grapeseed|peanut|rapeseed)\s+oil\b',
                  'extra-virgin olive oil', line, flags=re.I)

def _sub_sugar(line):
    l = re.sub(r'\b(?:white |granulated |caster |powdered |confectioners.? |light |dark )*(?:brown )?sugar\b'
               r'(?!\s*snap)', 'honey', line, flags=re.I)
    l = re.sub(r'\b(sucre|zucker)\b', 'honey', l, flags=re.I)
    return l

def _sub_sodium(line):
    l = line
    l = re.sub(r'\bsoy sauce\b', 'reduced-sodium soy sauce, to taste', l, flags=re.I)
    l = re.sub(r'\bfish sauce\b', 'fish sauce, to taste', l, flags=re.I)
    l = re.sub(r'\boyster sauce\b', 'oyster sauce, to taste', l, flags=re.I)
    l = re.sub(r'\b(bouillon|stock cube)\b', 'low-sodium broth', l, flags=re.I)
    l = re.sub(r'\b(hoisin|teriyaki)\b', r'\g<0>, to taste', l, flags=re.I)
    l = re.sub(r'\bdashi\b', 'low-sodium dashi', l, flags=re.I)
    return l

def _sub_mayo(line):
    return re.sub(r'\b(mayonnaise|mayonaise|mayo)\b', 'plain Greek yogurt', line, flags=re.I)

def _sub_tropical(line):
    l = re.sub(r'\b(coconut|palm) oil\b', 'extra-virgin olive oil', line, flags=re.I)
    l = re.sub(r'\bcoconut (milk|cream)\b', r'light coconut \1, to taste', l, flags=re.I)
    return l

def _sub_potato(line):
    if re.search(r'sweet potato', line, re.I):
        return line
    return re.sub(r'\bpotato(es)?\b', lambda m: 'sweet potato' + ('es' if m.group(1) else ''), line, flags=re.I)

LINE_SUB = {
    'REFINED_GRAIN': _sub_refined, 'BUTTER_CREAM': _sub_butter, 'NEUTRAL_OIL': _sub_neutral,
    'ADDED_SUGAR': _sub_sugar, 'SODIUM': _sub_sodium, 'MAYO': _sub_mayo, 'TROPICAL': _sub_tropical,
    'WHITE_POTATO': _sub_potato,
}

def line_groups(line):
    """Which penalty groups a single ingredient line triggers (reuses the real classifier)."""
    _, bad = S.classify([line])
    return {rec['group'] for rec in bad.values()}

def apply_group(ings, group):
    """Return (new_ingredients, changes) after applying one group's swap. changes: list of dicts."""
    changes = []
    if group == 'PROCESSED_MEAT':                       # drop the offending lines
        out = []
        for l in ings:
            if 'PROCESSED_MEAT' in line_groups(l):
                changes.append({'before': l, 'after': '(removed)'})
            else:
                out.append(l)
        return out, changes
    if group in ('FRIED', 'CHEESE_HEAVY'):              # method / quantity change, no line edit
        return ings, changes
    fn = LINE_SUB.get(group)
    if not fn:
        return ings, changes
    out = []
    for l in ings:
        if group in line_groups(l):
            n = fn(l)
            if n != l:
                changes.append({'before': l, 'after': n})
            out.append(n)
        else:
            out.append(l)
    return out, changes

def rescore(rec, ings, method_flags):
    r2 = dict(rec); r2['ingredients'] = ings
    return S.score_recipe(r2, force_no_fry=method_flags.get('FRIED', False),
                          force_no_cheese_heavy=method_flags.get('CHEESE_HEAVY', False))

# For desserts, swapping the butter/flour/sugar changes what the dish *is*, so we
# don't touch that structure — a "whole-wheat olive-oil madeleine" isn't a madeleine.
DESSERT_STRUCTURAL = {'BUTTER_CREAM', 'REFINED_GRAIN', 'ADDED_SUGAR'}

def improve(rec, orig):
    neg = orig['breakdown']['negative_by_group']
    candidates = [g for g in neg if g in SWAPPABLE]
    if orig.get('is_dessert'):
        candidates = [g for g in candidates if g not in DESSERT_STRUCTURAL]
    # single-swap gain for each candidate (actually re-score)
    scored_swaps = []
    for g in candidates:
        ings2, _ = apply_group(rec['ingredients'], g)
        s2 = rescore(rec, ings2, {g: True})
        gain = s2['score'] - orig['score']
        if gain >= 1:
            scored_swaps.append((gain, g))
    scored_swaps.sort(reverse=True)
    chosen = [g for _, g in scored_swaps[:MAX_SWAPS]]
    if not chosen:
        return None
    # apply chosen cumulatively
    ings = list(rec['ingredients']); all_changes = []; flags = {}; swap_desc = []
    for g in chosen:
        ings, ch = apply_group(ings, g)
        all_changes += ch
        if g in ('FRIED', 'CHEESE_HEAVY'):
            flags[g] = True
        swap_desc.append(SWAP_LABEL[g])
    improved = rescore(rec, ings, flags)
    return {
        'swaps': swap_desc, 'swap_groups': chosen,
        'changed_lines': all_changes,
        'improved_ingredients': ings,
        'improved_score': improved['score'], 'improved_grade': improved['grade'],
        'improved_bad': [{'ingredient': b['ingredient'], 'severity': b['severity']} for b in improved['bad_ingredients']],
    }

# ---------------------------------------------------------------------------
data = json.load(open(os.path.join(DATA, 'all_recipes.json')))
orig_scores = {r['name']: S.score_recipe(r) for r in data['recipes']}

results = []
for rec in data['recipes']:
    o = orig_scores[rec['name']]
    imp = improve(rec, o)
    row = {
        'name': rec['name'],
        'original_score': o['score'], 'original_grade': o['grade'],
        'original_bad': [{'ingredient': b['ingredient'], 'severity': b['severity'], 'penalty': b['penalty']}
                         for b in o['bad_ingredients']],
    }
    if imp:
        row.update({
            'improved_score': imp['improved_score'], 'improved_grade': imp['improved_grade'],
            'delta': imp['improved_score'] - o['score'],
            'swaps': imp['swaps'], 'changed_lines': imp['changed_lines'],
            'remaining_issues': imp['improved_bad'],
            'improved_ingredients': imp['improved_ingredients'],
        })
    else:
        # nothing to swap: either already clean, or only non-swappable issues (red meat / dessert)
        reasons = []
        rem = [b['ingredient'] for b in o['original_bad']] if False else [b['ingredient'] for b in o['bad_ingredients']]
        nb = {b['ingredient']: b for b in o['bad_ingredients']}
        neg = o['breakdown']['negative_by_group']
        if not neg:
            reasons.append('no flagged ingredients — already Mediterranean')
        if 'RED_MEAT' in neg:
            reasons.append('main issue is red meat, which defines the dish (not swappable)')
        if o['grade'] == 'A':
            reasons.append('already grade A')
        row.update({'improved_score': o['score'], 'improved_grade': o['grade'], 'delta': 0,
                    'swaps': [], 'changed_lines': [], 'no_swap_reason': '; '.join(reasons) or 'no clean swap available',
                    'remaining_issues': [{'ingredient': b['ingredient'], 'severity': b['severity']} for b in o['bad_ingredients']]})
    results.append(row)

results.sort(key=lambda x: (-x['delta'], -x['improved_score'], x['name'].lower()))

# ---- JSON ----
with open(os.path.join(DATA, 'recipe_improvements.json'), 'w', encoding='utf-8') as fh:
    json.dump({'recipe_count': len(results), 'max_swaps': MAX_SWAPS,
               'reference': 'mediterranean_scoring_system.md', 'recipes': results}, fh, ensure_ascii=False, indent=2)

# ---- Markdown ----
changed = [r for r in results if r['delta'] > 0]
unchanged = [r for r in results if r['delta'] == 0]
gained_grade = [r for r in changed if r['improved_grade'] != r['original_grade']]
SEV = {'SEVERE': '🔴', 'HIGH': '🟠', 'MODERATE': '🟡', 'MILD': '⚪'}

L = []
L.append('# Mediterranean-Ized Recipes — Improved Versions\n')
L.append('For every recipe, up to **%d** Mediterranean swaps were applied and the modified recipe '
         'was **re-scored**. We only swap an existing bad ingredient/method (or drop cured meat); '
         'red meat is left alone because it defines the dish, and olive oil is never added from nothing '
         '— only substituted for another fat.\n' % MAX_SWAPS)
L.append(f'- **{len(results)}** recipes processed\n- **{len(changed)}** improved by at least one swap\n'
         f'- **{len(gained_grade)}** moved up a letter grade\n'
         f'- Average gain among improved recipes: **+{round(sum(r["delta"] for r in changed)/max(1,len(changed)),1)}** points\n'
         f'- **{len(unchanged)}** needed no swap (already clean, already A, or only non-swappable issues like red meat)\n')

L.append('## Summary table (recipes with an improved version)\n')
L.append('| Recipe | Orig | → | New | Δ | Swaps |')
L.append('|---|---|---|---|---|---|')
for r in changed:
    grade_move = f"{r['original_grade']}→{r['improved_grade']}" if r['improved_grade'] != r['original_grade'] else r['original_grade']
    L.append(f"| {r['name']} | {r['original_score']} | {grade_move} | {r['improved_score']} | +{r['delta']} | "
             + '; '.join(r['swaps']) + ' |')
L.append('')

L.append('---\n\n## Detailed before → after\n')
for r in changed:
    L.append(f"### {r['name']} — {r['original_score']} ({r['original_grade']}) → {r['improved_score']} ({r['improved_grade']})  +{r['delta']}\n")
    L.append('**Swaps applied:**')
    for s in r['swaps']:
        L.append(f'- {s}')
    L.append('')
    if r['changed_lines']:
        L.append('**Ingredient changes:**')
        for c in r['changed_lines']:
            L.append(f'- `{c["before"]}` → `{c["after"]}`')
        L.append('')
    if r['remaining_issues']:
        L.append('**Still not ideal:** ' + ', '.join(f"{SEV.get(b['severity'],'')} {b['ingredient']}" for b in r['remaining_issues']) + '\n')
    else:
        L.append('**Remaining flags:** none — fully cleaned up.\n')

L.append('---\n\n## Recipes left unchanged\n')
L.append('| Recipe | Score | Grade | Why no swap |')
L.append('|---|---|---|---|')
for r in unchanged:
    L.append(f"| {r['name']} | {r['original_score']} | {r['original_grade']} | {r.get('no_swap_reason','')} |")

with open(os.path.join(DATA, 'recipe_improvements.md'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(L))

print(f'Processed {len(results)} recipes')
print(f'Improved: {len(changed)} | moved up a grade: {len(gained_grade)} | unchanged: {len(unchanged)}')
print(f'Avg gain (improved): +{round(sum(r["delta"] for r in changed)/max(1,len(changed)),1)}')
print('\nBiggest improvements:')
for r in changed[:12]:
    print(f"  {r['original_score']:3d}({r['original_grade']}) -> {r['improved_score']:3d}({r['improved_grade']})  +{r['delta']:2d}  {r['name']}")
