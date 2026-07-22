#!/usr/bin/env python3
"""Bundle the 6 data dimensions into one compact file for the web UI.

Writes web/data.js (a JS global, so web/index.html works by double-click via file://
AND when hosted on GitHub Pages). Merges everything the UI needs per recipe, joined
on `id`.
"""
import os, sys, re, json

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nutrition_engine as E, nutrition_match as M
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, 'data')
WEB = os.path.join(REPO, 'web')
os.makedirs(WEB, exist_ok=True)

# "staple" words most kitchens have / that aren't the shopping-list items — excluded
# from the "what can I cook" match so you aren't penalised for not listing salt.
STAPLES = set((
    'salt pepper oil olive water sugar flour butter vinegar baking soda powder yeast cornstarch '
    'stock broth honey syrup mustard mayonnaise ketchup soy sauce worcestershire '
    'cumin paprika turmeric cinnamon cardamom coriander oregano thyme basil rosemary parsley '
    'cilantro dill sage bay mint chili cayenne nutmeg clove ginger garlic sesame vanilla '
    'saffron masala curry seed flake herb spice zest extract breadcrumb panko '
    'broth bouillon stock'
).split())
# descriptors / noise that aren't the ingredient itself
NOISE = set((
    'for garnish grade sashimi style rehydrated costco sushi wide across plus more such loui louis '
    'quality good virgin extra sliced thinly finely roughly homemade store bought room temperature '
    'taste piece pieces half inch optional freshly toasted grated shredded crushed rinsed drained '
    'peeled seeded chopped diced minced sliced cut into thick thin large medium small skin bone '
    # recipe section-labels / fragments seen in oddly-formatted recipes
    'protein veggie base hearty pantry liquid aromatics topping section sea fine round moon broken '
    'floret cleaned hanout ras el spring light warm cold serving accompany note the'
).split())

# meat/poultry/fish keywords (backup to the Mediterranean group flags) — a vegetarian
# would avoid these (incl. stocks/broths made from them, gelatin, lard, fish sauce).
MEAT_FISH = ('beef steak pork lamb veal mutton oxtail brisket sirloin ribeye chuck carne mince '
             'chicken turkey duck goose poultry bacon ham prosciutto pancetta guanciale sausage '
             'salami chorizo pepperoni frankfurter andouille lardon kielbasa mortadella meatball '
             'fish salmon tuna cod tilapia halibut sole snapper haddock pollock trout sardine '
             'mackerel anchovy anchovies herring shrimp prawn prawns squid calamari octopus mussel '
             'clam oyster scallop crab lobster seafood gelatin lard tallow suet '
             'boeuf porc agneau jambon poulet poisson saumon crevette').split()
_MEAT_RE = re.compile(r'(?<![a-z])(' + '|'.join(map(re.escape, MEAT_FISH)) + r')(?![a-z])')

# meat/fish words used only in a broth/stock don't make a dish non-vegetarian
# (a lentil soup made with chicken stock still counts as vegetarian here).
_BROTH_RE = re.compile(r'(?:chicken|beef|pork|fish|turkey|veal|lamb|vegetable|bone|ham|shrimp|dashi)'
                       r'\s+(?:broth|stock|bouillon|consomm\w*|base)')

def is_vegetarian(recipe, m):
    posg = (m.get('breakdown') or {}).get('positive_by_group', {})
    negg = (m.get('breakdown') or {}).get('negative_by_group', {})
    # These groups are already broth-safe in the Mediterranean scorer (chicken/beef
    # broth/stock don't set them). FISH stays strict (fish sauce/stock = not vegetarian).
    if any(g in negg for g in ('RED_MEAT', 'PROCESSED_MEAT')) or any(g in posg for g in ('POULTRY', 'FISH')):
        return False
    text = _BROTH_RE.sub(' ', ' '.join(recipe.get('ingredients') or []).lower())
    return not _MEAT_RE.search(text)

# --- personal profile flags (from PROFILE.md): allergens (avoid) + soft prefs (caution) ---
_COOK = r'(saut|wilt|cook|steam|boil|bake|braise|blanch|fry|simmer|roast|creamed)'

def profile_flags(recipe, dtype):
    ing = ' '.join(recipe.get('ingredients') or []).lower()
    dirs = ' '.join(recipe.get('directions') or []).lower()
    name = (recipe.get('name') or '').lower()
    both = ing + ' ' + dirs + ' ' + name
    avoid, caution = [], []

    # cooked spinach — raw baby-spinach salad is fine
    if re.search(r'\bspinach\b', ing):
        raw_salad = 'salad' in dtype and not re.search(
            _COOK + r'[^.]{0,25}spinach|spinach[^.]{0,25}' + _COOK, ing + ' ' + dirs)
        if not raw_salad:
            avoid.append('cooked spinach')

    # fresh mint crushed/muddled — whole-leaf garnish / dry mint are fine.
    # Only hard-flag when the crush/muddle is ACTUALLY on the mint (or a mint-based sauce).
    if re.search(r'\bmint\b', ing) and not re.search(r'dried mint|dry mint', ing):
        if re.search(r'mojito|mint pesto|mint sauce|mint chutney', name + ' ' + ing) or re.search(
                r'(muddl|crush|puree|purée|juic)\w*[^.]{0,25}\bmint|\bmint\b[^.]{0,25}(muddl|crush|puree|purée|juic)', both):
            avoid.append('crushed/muddled fresh mint')
        else:
            caution.append('has mint — fine as a whole-leaf garnish (pluck it), not if crushed in')

    # raw bell pepper as a main
    if 'gazpacho' in name:
        avoid.append('raw bell pepper (gazpacho)')
    elif re.search(r'bell pepper|red pepper|green pepper|capsicum', ing) \
            and re.search(r'salsa|slaw|raw', name + ' ' + ing) and not re.search(_COOK, dirs):
        caution.append('may have raw bell pepper — check')

    # shrimp-forward (likes shrimp, just not shrimp-heavy)
    if re.search(r'\bshrimp\b|\bprawn', name):
        caution.append('shrimp-forward — you like it lighter on shrimp')

    # oysters / bivalves — seafood 'scallops' (plural) only, so the pastry verb "scallop the
    # edges" doesn't match; and exclude oyster sauce / oyster mushroom
    if re.search(r'\b(clams?|mussels?|scallops)\b|\b(sea|bay)\s+scallops?\b', both):
        only_sauce = re.search(r'\boysters?\b', both) and not re.search(r'\b(clams?|mussels?|scallops)\b', both) \
            and re.search(r'oyster sauce|oyster mushroom', both)
        if not only_sauce:
            caution.append('shellfish (oyster/clam/mussel/scallop) — you usually skip these')

    return {'avoid': avoid, 'caution': caution}

def core_ingredients(recipe):
    """Distinct non-staple food words a shopper would need — the 'what to cook' keys."""
    seen = []
    for line in recipe.get('ingredients') or []:
        if E.SKIP_LINE.match(line):
            continue
        _, _, name = E.parse_amount(line)
        toks = [w for w in M.normalize(name or '')
                if len(w) > 2 and w not in STAPLES and w not in NOISE and w not in M.LEAD_ADJ]
        for w in toks:
            if w not in seen:
                seen.append(w)
    return seen

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
        'core': core_ingredients(r),            # non-staple food words, for "what to cook"
        'veg': is_vegetarian(r, m),             # True = vegetarian (no meat/poultry/fish)
        'pf': profile_flags(r, ix.get('dish_type') or n.get('dish_type') or ''),  # personal allergen/pref flags
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
