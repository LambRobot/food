#!/usr/bin/env python3
"""Nutrition & health engine.

For each recipe: parse ingredient lines -> match to USDA foods -> convert to grams
-> sum nutrients -> per serving -> health scores. Fully offline (reads the committed
data/usda_reference.json). See nutrition_methodology_wiki.md / nutrition_engine_plan.md.

v1: full macros + micronutrients + Nutri-Score + NRF9.3 nutrient density + NOVA
processing estimate. HEI-2020 scaffolded (null) for a later pass. Cooking yield/
retention factors are NOT applied yet (USDA retention values live in a separate PDF
table, not the bulk CSV) — see the caveat in the output.
"""
import os, re, json, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nutrition_match as M

REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, 'data')

# ---- unit tables --------------------------------------------------------------
MASS_G = {'g': 1, 'gram': 1, 'grams': 1, 'gramm': 1, 'gramme': 1, 'grammes': 1, 'mg': .001,
          'kg': 1000, 'kilogram': 1000, 'oz': 28.35, 'ounce': 28.35, 'ounces': 28.35,
          'lb': 453.6, 'lbs': 453.6, 'pound': 453.6, 'pounds': 453.6}
VOL_ML = {'cup': 236.6, 'cups': 236.6, 'tablespoon': 14.79, 'tablespoons': 14.79, 'tbsp': 14.79,
          'teaspoon': 4.93, 'teaspoons': 4.93, 'tsp': 4.93, 'ml': 1, 'milliliter': 1, 'cl': 10,
          'dl': 100, 'l': 1000, 'liter': 1000, 'litre': 1000, 'pint': 473, 'quart': 946,
          'gallon': 3785, 'fl oz': 29.57, 'fluid ounce': 29.57,
          'teelöffel': 4.93, 'teeloffel': 4.93, 'esslöffel': 14.79, 'essloffel': 14.79, 'tasse': 236.6}
# g/ml densities by keyword (fallback when USDA lacks a matching portion)
DENSITY = [('oil', .91), ('butter', .91), ('honey', 1.42), ('syrup', 1.37), ('molasses', 1.4),
           ('brown sugar', .9), ('sugar', .85), ('flour', .53), ('cornstarch', .63), ('cocoa', .53),
           ('bread crumb', .4), ('panko', .25), ('oat', .41), ('rice', .85), ('salt', 1.22),
           ('milk', 1.03), ('cream', 1.0), ('yogurt', 1.03), ('stock', 1.0), ('broth', 1.0),
           ('juice', 1.04), ('wine', .99), ('vinegar', 1.01), ('soy sauce', 1.15), ('water', 1.0)]
# grams per single item (count with no unit), by keyword
COUNT_G = [('egg yolk', 18), ('egg white', 33), ('egg', 50), ('garlic', 3), ('shallot', 30),
           ('green onion', 15), ('scallion', 15), ('spring onion', 15), ('onion', 110),
           ('sweet potato', 130), ('potato', 170), ('tomato', 123), ('carrot', 61), ('celery', 40),
           ('lemon', 58), ('lime', 67), ('orange', 131), ('apple', 182), ('banana', 118),
           ('avocado', 150), ('bell pepper', 119), ('jalapeno', 14), ('chile', 45), ('chili', 45),
           ('pepper', 30), ('cucumber', 300), ('zucchini', 196), ('eggplant', 458), ('leek', 89),
           ('fennel', 234), ('artichoke', 128), ('mushroom', 18), ('chicken breast', 174),
           ('chicken thigh', 130), ('bacon', 8), ('bread', 28), ('bay lea', 0.2), ('olive', 4),
           ('anchovy', 4), ('fig', 50), ('date', 24), ('apricot', 35), ('beet', 82), ('corn', 145),
           ('ginger', 30), ('parsnip', 133), ('turnip', 122), ('sausage', 75), ('can', 400),
           # portion-size cuts first (so "tenderloin steak" -> steak, not whole tenderloin)
           ('steak', 250), ('chop', 180), ('cutlet', 150), ('fillet', 170), ('filet', 170),
           ('breast', 174), ('thigh', 130), ('drumstick', 90),
           # whole cuts / large items when no weight is given (typical sizes)
           ('rack', 1100), ('rib', 1100), ('brisket', 2000), ('pork shoulder', 2000),
           ('leg of lamb', 2500), ('whole chicken', 1400), ('turkey', 5000), ('roast', 1500),
           ('tenderloin', 500), ('pork loin', 1200), ('loin', 1000)]
FRAC = {'½': .5, '¼': .25, '¾': .75, '⅓': 1/3, '⅔': 2/3, '⅛': .125, '⅜': .375, '⅝': .625, '⅞': .875, '⅕': .2}
FVLN_CATS = {'9', '11', '12', '16'}   # USDA: fruits, vegetables, nuts/seeds, legumes

VAGUE = re.compile(r'to taste|for garnish|for serving|as needed|optional|pinch|dash|a splash|drizzle')

@lru_cache(maxsize=4096)
def match_cached(name):
    return M.match(name)

def _defrac(s):
    """Resolve unicode fractions, combining an integer prefix: '1 ½' -> '1.5'."""
    for ch, val in FRAC.items():
        s = re.sub(r'(\d+)\s*' + ch, lambda m: str(round(int(m.group(1)) + val, 4)), s)
        s = s.replace(ch, ' ' + str(round(val, 4)))
    return s

def parse_amount(text):
    """Return (amount_float_or_None, unit_or_None, name_text)."""
    # "Onion: 1 large, diced" (label: qty desc) -> reorder so the quantity leads
    m = re.match(r'^\s*([A-Za-z][A-Za-z &/\'-]{1,28}):\s*(.+)$', text)
    if m and not any(c.isdigit() for c in m.group(1)) and len(m.group(1).split()) <= 4:
        text = m.group(2).strip() + ', ' + m.group(1).strip()
    s = _defrac(text.strip()).strip()
    s = re.sub(r'^[\-–—\*•·▪●]+\s*', '', s)   # strip leading bullets/dashes
    s = re.sub(r'(\d)\s*#', r'\1 lb ', s)              # "3#" / "3-5#" -> pounds
    s = re.sub(r'(\d)\s*-\s*(?=[a-zA-Z])', r'\1 ', s)   # "3-pound" -> "3 pound" (keep "2-3")
    # prefer an explicit weight/volume in parentheses e.g. "1 (14 oz) can" -> 14 oz
    mp = re.search(r'\((\d+(?:\.\d+)?)\s*-?\s*(\d*(?:\.\d+)?)\s*(oz|ounce|ounces|g|gram|grams|lb|pound|pounds|kg|ml|l)\b', s, re.I)
    paren = None
    if mp:
        a = float(mp.group(1)); unit = mp.group(3).lower()
        paren = (a, unit)
    # leading quantity: "1 1/2", "1.5", "2-3", "1/2", "1"
    m = re.match(r'\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)', s)                # pure fraction 1/2
    amount = None; rest = s
    if m and float(m.group(2)) != 0:
        amount = float(m.group(1)) / float(m.group(2)); rest = s[m.end():]
    else:
        m = re.match(r'\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)', s)  # mixed 1 1/2
        if m and float(m.group(3)) != 0:
            amount = float(m.group(1)) + float(m.group(2)) / float(m.group(3)); rest = s[m.end():]
        else:
            m = re.match(r'\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', s)         # range 2-3
            if m:
                amount = (float(m.group(1)) + float(m.group(2))) / 2; rest = s[m.end():]
            else:
                m = re.match(r'\s*(\d+(?:\.\d+)?)', s)                    # plain number
                if m:
                    amount = float(m.group(1)); rest = s[m.end():]
    rest = re.sub(r'\([^)]*\)', ' ', rest)                        # drop parentheticals from name
    # unit word
    unit = None
    mu = re.match(r'\s*([a-zA-Z]+)\b', rest)
    if mu:
        w = mu.group(1).lower()
        if w in MASS_G or w in VOL_ML or w in ('clove', 'cloves', 'slice', 'slices', 'stick',
                'sticks', 'can', 'cans', 'sprig', 'sprigs', 'head', 'stalk', 'stalks', 'bunch',
                'piece', 'pieces', 'fillet', 'fillets', 'strip', 'strips', 'package', 'jar'):
            unit = w; rest = rest[mu.end():]
    if paren and (unit in ('can', 'cans', None) or amount == 1):
        amount, unit = paren                                     # use the real can/pack size
    name = re.sub(r'^\s*(of|de|the)\s+', '', rest).strip(' ,.-')
    return amount, unit, name

def density_for(name):
    for kw, d in DENSITY:
        if kw in name:
            return d
    return 1.0

def count_weight(name):
    for kw, g in COUNT_G:
        if kw in name:
            return g
    return None

def portion_grams(food, unit):
    """grams for 1 `unit` from USDA portions, else None."""
    if not unit:
        return None
    u = unit.rstrip('s')
    for p in food.get('portions', []):
        pu = (p.get('unit') or '').lower().rstrip('s')
        mod = (p.get('modifier') or '').lower()
        if pu == u or (u and u in mod):
            amt = p.get('amount') or 1
            if amt:
                return p['grams'] / amt
    return None

def to_grams(amount, unit, name, food):
    """Return (grams, confidence 0-1)."""
    if amount is None:
        return (2.0, 0.3)                      # unquantified but present (e.g. "salt")
    if unit in MASS_G:
        return (amount * MASS_G[unit], 1.0)
    if unit in VOL_ML:
        ml = amount * VOL_ML[unit]
        if food:
            pg = portion_grams(food, unit)
            if pg:
                return (amount * pg, 0.9)
        return (ml * density_for(name), 0.7)
    # spices/herbs measured by count (pods, leaves, sticks, whole) are tiny, not 75 g each
    if food and food.get('cat') == '2':
        return (min(amount * 1.5, 6.0), 0.4)
    # count / container units or no unit
    if food:
        pg = portion_grams(food, unit or '')
        if pg:
            return (amount * pg, 0.85)
    cw = count_weight(name)
    if unit in ('clove', 'cloves'):
        return (amount * (3 if 'garlic' in name else (cw or 3)), 0.8)
    if unit in ('slice', 'slices'):
        return (amount * (cw or 20), 0.5)
    if unit in ('can', 'cans'):
        # canned beans/legumes are sold ~15 oz, ~255 g drained; other cans ~400 g
        legume = any(w in name for w in ('bean', 'chickpea', 'garbanzo', 'lentil', 'pinto', 'cannellini'))
        return (amount * (255 if legume else 400), 0.5)
    if unit in ('stick', 'sticks') and 'butter' in name:
        return (amount * 113, 0.7)
    # no recognized unit: a count of items, or a bare number the writer meant as grams
    if unit is None:
        if cw and amount <= 40:
            return (amount * cw, 0.6)
        if amount > 25:
            return (amount, 0.4)               # bare large number ≈ grams (unit omitted)
        if cw:
            return (amount * cw, 0.6)
    return (amount * 75, 0.25)                  # unknown item weight — low confidence

# ---- Nutri-Score (2017 general-food algorithm) --------------------------------
def _pts(value, thresholds):
    p = 0
    for t in thresholds:
        if value > t:
            p += 1
    return p
N_ENERGY = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]   # kJ/100g
N_SUGAR = [4.5, 9, 13.5, 18, 22.5, 27, 31, 36, 40, 45]
N_SATFAT = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
N_SODIUM = [90, 180, 270, 360, 450, 540, 630, 720, 810, 900]            # mg/100g
P_FIBER = [0.9, 1.9, 2.8, 3.7, 4.7]                                     # AOAC g/100g
P_PROTEIN = [1.6, 3.2, 4.8, 6.4, 8.0]

def nutri_score(per100, fvln_frac):
    kj = per100.get('kcal', 0) * 4.184
    N = (_pts(kj, N_ENERGY) + _pts(per100.get('sugar', 0), N_SUGAR)
         + _pts(per100.get('sat_fat', 0), N_SATFAT) + _pts(per100.get('sodium', 0), N_SODIUM))
    fvln_pct = fvln_frac * 100
    fvln_pts = 5 if fvln_pct > 80 else (2 if fvln_pct > 60 else (1 if fvln_pct > 40 else 0))
    fiber_pts = _pts(per100.get('fiber', 0), P_FIBER)
    protein_pts = _pts(per100.get('protein', 0), P_PROTEIN)
    P = fvln_pts + fiber_pts
    if N >= 11 and fvln_pts < 5:
        pass                                     # protein not counted
    else:
        P += protein_pts
    score = N - P
    grade = 'A' if score <= -1 else 'B' if score <= 2 else 'C' if score <= 10 else 'D' if score <= 18 else 'E'
    return {'grade': grade, 'points': score,
            'detail': {'negative': N, 'positive': P, 'fvln_pct': round(fvln_pct)}}

# ---- NRF9.3 nutrient density --------------------------------------------------
DV = {'protein': 50, 'fiber': 28, 'vit_a_rae': 900, 'vit_c': 90, 'vit_e': 15, 'calcium': 1300,
      'iron': 18, 'magnesium': 420, 'potassium': 4700}
LIM = {'sat_fat': 20, 'sugar': 50, 'sodium': 2300}

def nrf9_3(per100, kcal100):
    if kcal100 <= 0:
        return None
    f = 100 / kcal100                            # scale to per 100 kcal
    pos = sum(min((per100.get(n, 0) * f) / dv * 100, 100) for n, dv in DV.items())
    neg = sum((per100.get(n, 0) * f) / dv * 100 for n, dv in LIM.items())
    return round(pos - neg, 1)

# ---- NOVA processing estimate (heuristic) -------------------------------------
ULTRA = ['condensed milk', 'corn syrup', 'hot dog', 'soda', 'bouillon', 'instant', 'processed cheese',
         'margarine', 'shortening', 'hydrogenated', 'nugget', 'packaged', 'cake mix', 'cool whip',
         'marshmallow', 'sausage', 'bacon', 'salami', 'pepperoni', 'chip', 'cracker']
CULINARY = ['oil', 'butter', 'sugar', 'salt', 'honey', 'syrup', 'vinegar', 'flour', 'starch', 'cream']

def nova_group(ingredient_names):
    joined = ' | '.join(ingredient_names)
    if any(u in joined for u in ULTRA):
        return 4
    whole = sum(1 for n in ingredient_names if not any(c in n for c in CULINARY))
    return 1 if whole >= max(3, 0.7 * len(ingredient_names)) else 3

# ---- cooking method + nutrient retention (USDA Release 6, representative) ------
# fraction of a nutrient RETAINED by cooking method; macros/minerals ~conserved,
# water-soluble vitamins lose the most (esp. by boiling). Unlisted nutrient => 1.0.
RETENTION = {
    'boil':  {'vit_c': .55, 'folate': .60, 'thiamin': .70, 'riboflavin': .80, 'niacin': .75,
              'vit_b6': .75, 'vit_b12': .85, 'vit_a_rae': .85, 'vit_e': .90, 'potassium': .70,
              'magnesium': .80, 'calcium': .90, 'iron': .90, 'zinc': .90, 'phosphorus': .85},
    'steam': {'vit_c': .75, 'folate': .75, 'thiamin': .85, 'riboflavin': .90, 'niacin': .85,
              'vit_b6': .85, 'vit_a_rae': .90, 'potassium': .90, 'magnesium': .90},
    'roast': {'vit_c': .75, 'folate': .75, 'thiamin': .80, 'riboflavin': .90, 'niacin': .85,
              'vit_b6': .80, 'vit_b12': .90, 'vit_a_rae': .85, 'vit_e': .85, 'potassium': .90},
    'fry':   {'vit_c': .75, 'folate': .70, 'thiamin': .80, 'riboflavin': .85, 'niacin': .85,
              'vit_b6': .75, 'vit_a_rae': .80, 'vit_e': .70, 'folate': .80},
    'saute': {'vit_c': .80, 'folate': .80, 'thiamin': .85, 'riboflavin': .90, 'niacin': .90,
              'vit_b6': .85, 'vit_a_rae': .90, 'vit_e': .85, 'potassium': .95},
    'grill': {'vit_c': .75, 'folate': .75, 'thiamin': .75, 'riboflavin': .85, 'niacin': .85,
              'vit_b6': .80, 'vit_b12': .85, 'vit_a_rae': .85},
    'none':  {},
}
METHOD_KW = [('fry', ['deep-fr', 'deep fr', 'fried', 'fryer', 'fry ']),
             ('boil', ['boil', 'simmer', 'braise', 'stew', 'poach', 'soup', 'broth', 'slow cook', 'pressure cook']),
             ('roast', ['roast', 'bake', 'oven', 'sheet pan']),
             ('grill', ['grill', 'broil', 'barbecue', 'bbq', 'smoke', 'char']),
             ('steam', ['steam']),
             ('saute', ['saut', 'stir-fry', 'stir fry', 'pan-fry', 'pan fry', 'sear', 'sweat', 'fry until'])]

def cooking_method(recipe):
    text = (' '.join(recipe.get('directions') or []) + ' ' + (recipe['name'] or '')).lower()
    counts = {m: sum(text.count(k) for k in kws) for m, kws in METHOD_KW}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else 'none'

def apply_retention(totals, method):
    factors = RETENTION.get(method, {})
    for nutrient, frac in factors.items():
        if nutrient in totals:
            totals[nutrient] *= frac
    return totals

# ---- food groups (for HEI) ----------------------------------------------------
CAT_GROUP = {'9': 'fruit', '11': 'veg', '16': 'legume', '12': 'nuts', '1': 'dairy_egg',
             '20': 'grain', '18': 'grain', '5': 'poultry', '10': 'meat', '13': 'meat',
             '7': 'meat', '15': 'seafood', '19': 'sweets', '4': 'fat', '2': 'spice'}
WHOLE_GRAIN_KW = ['whole', 'brown rice', 'wild rice', 'oat', 'quinoa', 'bulgur', 'barley', 'buckwheat',
                  'farro', 'millet', 'rye', 'spelt', 'wheat berr']

def _lin(x, lo, hi, pts, higher_better=True):
    """Linear HEI component score between lo (0 pts) and hi (max pts)."""
    if higher_better:
        if x >= hi: return pts
        if x <= lo: return 0.0
        return pts * (x - lo) / (hi - lo)
    else:  # moderation: max pts at lo, 0 at hi
        if x <= lo: return pts
        if x >= hi: return 0.0
        return pts * (hi - x) / (hi - lo)

def hei_2020(totals, groups, whole_g, refined_g):
    """Approximate HEI-2020 (0-100). Moderation components are nutrient-accurate;
    adequacy components use gram->cup/oz-equivalent proxies (true HEI needs FPED)."""
    kcal = totals.get('kcal', 0)
    if kcal < 50:
        return None
    k = 1000.0 / kcal                                  # per-1000-kcal scaler
    fruit_ce = groups.get('fruit', 0) / 125.0
    veg_ce = (groups.get('veg', 0) + groups.get('legume', 0)) / 125.0
    gb_ce = groups.get('legume', 0) / 125.0
    wg_oz = whole_g / 28.0
    dairy_ce = groups.get('dairy_egg', 0) / 244.0
    prot_oz = (groups.get('meat', 0) + groups.get('poultry', 0) + groups.get('seafood', 0)
               + groups.get('legume', 0) + groups.get('nuts', 0)) / 28.0
    seaplant_oz = (groups.get('seafood', 0) + groups.get('legume', 0) + groups.get('nuts', 0)) / 28.0
    rg_oz = refined_g / 28.0
    unsat = max(totals.get('fat', 0) - totals.get('sat_fat', 0), 0)
    fa_ratio = unsat / totals['sat_fat'] if totals.get('sat_fat', 0) > 0 else 3.0
    sodium_g = totals.get('sodium', 0) / 1000.0
    # estimate ADDED sugar = total - intrinsic (fruit ~10 g/100g, dairy ~5 g/100g)
    intrinsic = groups.get('fruit', 0) * 0.10 + groups.get('dairy_egg', 0) * 0.05
    added_sugar_g = max(0, totals.get('sugar', 0) - intrinsic)
    addsugar_pct = (added_sugar_g * 4) / kcal * 100 if kcal else 0
    satfat_pct = (totals.get('sat_fat', 0) * 9) / kcal * 100 if kcal else 0

    c = {
        'total_fruits': _lin(fruit_ce * k, 0, 0.8, 5),
        'whole_fruits': _lin(fruit_ce * k, 0, 0.4, 5),
        'total_vegetables': _lin(veg_ce * k, 0, 1.1, 5),
        'greens_beans': _lin(gb_ce * k, 0, 0.2, 5),
        'whole_grains': _lin(wg_oz * k, 0, 1.5, 10),
        'dairy': _lin(dairy_ce * k, 0, 1.3, 10),
        'total_protein': _lin(prot_oz * k, 0, 2.5, 5),
        'seafood_plant_protein': _lin(seaplant_oz * k, 0, 0.8, 5),
        'fatty_acids': _lin(fa_ratio, 1.2, 2.5, 10),
        'refined_grains': _lin(rg_oz * k, 1.8, 4.3, 10, higher_better=False),
        'sodium': _lin(sodium_g * k, 1.1, 2.0, 10, higher_better=False),
        'added_sugars': _lin(addsugar_pct, 6.5, 26, 10, higher_better=False),
        'saturated_fats': _lin(satfat_pct, 8, 16, 10, higher_better=False),
    }
    return {'total': round(sum(c.values())), 'components': {k2: round(v, 1) for k2, v in c.items()},
            'note': 'approximate (gram->cup/oz-eq proxies; added sugar ≈ total sugar)'}

# ---- our own serving estimate (source servings are unreliable, so we ignore them) ----
# Standard finished-dish weight per serving (grams) by dish type. Servings =
# total edible weight / this. Far more consistent than the source's "Serving: 1".
PORTION_G = {'main': 400, 'soup/stew': 450, 'salad': 150, 'side': 130,
             'sauce/condiment': 55, 'bread/baked': 70, 'dessert': 115, 'drink': 250,
             'breakfast': 300}
_DESSERT_KW = ['cake', 'cookie', 'ice cream', 'pie', 'tart', 'brownie', 'cupcake', 'pudding',
               'mousse', 'cheesecake', 'scone', 'muffin', 'pavlova', 'frangipane', 'custard',
               'pops', 'financier', 'madeleine', 'galette', 'speculoos', 'dessert', 'frosting']

def dish_type(recipe):
    n = (recipe.get('name') or '').lower()
    c = ' '.join(recipe.get('categories') or []).lower()
    def hit(*ws): return any(w in n or w in c for w in ws)
    if hit(*_DESSERT_KW): return 'dessert'
    if hit('cocktail', 'margarita', 'smoothie', 'juice', 'drink', 'eggnog'): return 'drink'
    if hit('bread', 'focaccia', 'sourdough', 'baguette', 'brioche', 'rolls', 'buns', 'loaf', 'naan', 'muffin'): return 'bread/baked'
    # a dish with a protein served "in/with ... sauce" is a MAIN, not a condiment
    # ("Basil Chicken in Coconut Curry Sauce"); only standalone sauces are condiments
    protein_main = hit('chicken', 'beef', 'pork', 'lamb', 'turkey', 'duck', 'shrimp', 'fish',
                       'salmon', 'tofu', 'meatball', 'veal') and hit('in ', 'with', 'braised', 'simmered')
    if not protein_main and hit('sauce', 'dressing', 'marinade', 'pesto', 'ketchup', 'mayo', 'salsa',
                                'dip', 'chutney', 'vinaigrette', 'béchamel', 'jam', 'curd', 'nappage', 'aioli'):
        return 'sauce/condiment'
    if hit('salad', 'slaw', 'kachumber'): return 'salad'
    if hit('soup', 'stew', 'broth', 'chowder', 'bisque', 'gumbo', 'ramen', 'pho', 'caldo', 'chili'): return 'soup/stew'
    if hit('breakfast', 'pancake', 'waffle', 'oatmeal', 'granola', 'shakshuka', 'quiche'): return 'breakfast'
    # only clear accompaniments are 'side'; one-pot grain/legume dishes are mains
    if hit('side', 'slaw', 'pickle', 'broccolini', 'sautéed', 'sauteed', 'roasted vegetable',
           'green beans', 'asparagus', 'brussels', 'greens'): return 'side'
    return 'main'

def estimate_servings(total_g, dtype):
    per = PORTION_G.get(dtype, 380)
    return max(1, min(60, round(total_g / per))) if total_g > 0 else 4

# ---- per-recipe ---------------------------------------------------------------
SKIP_LINE = re.compile(r'^\s*(ingredients?\s+save\s+recipe|save\s+recipe|for the\b|to serve\b)', re.I)
NUTRIENT_KEYS = ['kcal', 'protein', 'fat', 'sat_fat', 'trans_fat', 'carb', 'fiber', 'sugar',
                 'sodium', 'cholesterol', 'calcium', 'iron', 'magnesium', 'phosphorus', 'potassium',
                 'zinc', 'vit_a_rae', 'vit_c', 'vit_d', 'vit_e', 'vit_k', 'folate', 'thiamin',
                 'riboflavin', 'niacin', 'vit_b6', 'vit_b12']

def parse_servings(s):
    if not s:
        return None
    t = s.lower()
    if 'dozen' in t:
        m = re.search(r'(\d+)\s*dozen', t)
        return (int(m.group(1)) if m else 1) * 12
    # explicit piece/serving count wins (handles "... or 22 cupcakes")
    m = re.search(r'(\d+)\s*(cupcakes|muffins|cookies|pieces|servings|slices|people|personnes|portions|serves)', t)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*(?:to|-|–|—)\s*(\d+)', t)      # range -> average
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi > 40 or (lo > 0 and hi / lo > 5):            # garbled range (e.g. "6-835")
            return lo
        return round((lo + hi) / 2)
    # yield stated only as volume ("about 2 cups", "yield 2 cups") -> ~4 servings/cup
    m = re.search(r'(\d+(?:\.\d+)?)\s*cups?\b', t)
    if m and not re.search(r'\d+\s*(serv|portion|person|people|slice|piece)', t):
        return max(1, round(float(m.group(1)) * 4))
    m = re.search(r'\d+', t)
    if not m:
        return None
    n = int(m.group(0))
    if n == 1:                                             # "1 cake/loaf/pie" -> typical slices
        for w, slices in [('cheesecake', 12), ('cake', 12), ('loaf', 10), ('pie', 8), ('tart', 8),
                          ('bread', 12), ('pan', 9), ('batch', 12), ('dish', 6), ('casserole', 6),
                          ('quiche', 6), ('galette', 8)]:
            if w in t:
                return slices
    return n

def analyze(recipe):
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    total_g = matched_g = fvln_g = gconf_weighted = 0.0
    groups = {}
    whole_g = refined_g = 0.0
    unmatched = []
    method = cooking_method(recipe)
    for line in recipe['ingredients']:
        if SKIP_LINE.match(line):
            continue
        amount, unit, name = parse_amount(line)
        if not name:
            continue
        fid, food, conf = match_cached(name)
        grams, gconf = to_grams(amount, unit, name.lower(), food)
        # garnish / to-taste amounts with no real measure are negligible
        if VAGUE.search(line) and unit not in MASS_G and unit not in VOL_ML:
            grams = min(grams, 1.0)
        # deep-frying: only ~12% of the frying oil is absorbed, not the whole batch
        if method == 'fry' and 'oil' in name.lower() and grams > 80 and \
                (re.search(r'\bfry|frying|deep|fryer\b', line.lower()) or grams > 200):
            grams *= 0.12
        # dried legumes/grains measured DRY but matched to a COOKED USDA form are ~2.7x
        # more nutrient-dense per gram (less water) — correct the density
        if food and re.search(r'\b(dried|dry)\b', line, re.I) and 'cooked' in food['desc'].lower() \
                and any(w in food['desc'].lower() for w in ('bean', 'lentil', 'chickpea', 'pea')):
            grams *= 2.7
        total_g += grams
        if not food:
            unmatched.append(name)
            continue
        matched_g += grams
        gconf_weighted += grams * gconf
        if food.get('cat') in FVLN_CATS:
            fvln_g += grams
        grp = CAT_GROUP.get(food.get('cat'))
        if grp:
            groups[grp] = groups.get(grp, 0) + grams
            if grp == 'grain':
                if any(w in food['desc'].lower() for w in WHOLE_GRAIN_KW):
                    whole_g += grams
                else:
                    refined_g += grams
        # apply cooking nutrient-retention ONLY to raw-matched foods — foods already
        # matched in a cooked USDA form already reflect those losses (no double-discount)
        raw = not any(w in food['desc'].lower() for w in ('cooked', 'boiled', 'roasted', 'baked', 'braised', 'grilled'))
        rf = RETENTION.get(method, {}) if raw else {}
        per100 = food['n']
        for k in NUTRIENT_KEYS:
            if k in per100:
                totals[k] += grams / 100.0 * per100[k] * rf.get(k, 1.0)

    hei = hei_2020(totals, groups, whole_g, refined_g)
    # Our own serving count from total weight — source servings are ignored (kept for reference).
    dtype = dish_type(recipe)
    source_serv = parse_servings(recipe.get('servings'))
    servings = estimate_servings(total_g, dtype)
    serv_note = (f'servings estimated as {servings} from total weight '
                 f'(~{round(total_g)} g / {PORTION_G.get(dtype, 380)} g per {dtype} serving); '
                 f'source stated {recipe.get("servings")!r}')
    cure_note = None
    if totals.get('sodium', 0) / servings > 5000:
        cure_note = 'very high sodium — likely a cure/brine (mostly rinsed off, not consumed)'
    per_serv = {k: totals[k] / servings for k in NUTRIENT_KEYS}
    per_100g = {k: (totals[k] / total_g * 100 if total_g else 0) for k in NUTRIENT_KEYS}
    coverage = matched_g / total_g if total_g else 0
    gram_conf = gconf_weighted / matched_g if matched_g else 0
    overall = coverage * (0.5 + 0.5 * gram_conf)   # penalize weak gram estimates
    fvln_frac = fvln_g / matched_g if matched_g else 0
    confidence = 'low' if cure_note else ('high' if overall >= 0.8 else 'medium' if overall >= 0.55 else 'low')
    # uncertainty band from the MEASURED calibration error per confidence tier
    unc = {'high': 0.20, 'medium': 0.30, 'low': 0.50}[confidence]

    ns = nutri_score(per_100g, fvln_frac)
    nrf = nrf9_3(per_100g, per_100g.get('kcal', 0))
    nova = nova_group([n.lower() for n in recipe['ingredients']])

    def r(x, d=0):
        return round(x, d) if d else round(x)
    return {
        'id': recipe.get('id'), 'name': recipe['name'],
        'servings': servings,                     # our estimate (source servings ignored)
        'source_servings': recipe.get('servings'),
        'dish_type': dtype,
        'out_of_scope': bool(recipe.get('out_of_scope')),
        'out_of_scope_reason': recipe.get('out_of_scope_reason'),
        'total_kcal': r(totals['kcal']),          # whole recipe (all servings)
        'kcal_range': [r(per_serv['kcal'] * (1 - unc)), r(per_serv['kcal'] * (1 + unc))],
        'uncertainty_pct': round(unc * 100),
        'per_serving': {
            'kcal': r(per_serv['kcal']), 'protein_g': r(per_serv['protein'], 1),
            'carb_g': r(per_serv['carb'], 1), 'fiber_g': r(per_serv['fiber'], 1),
            'sugar_g': r(per_serv['sugar'], 1), 'fat_g': r(per_serv['fat'], 1),
            'sat_fat_g': r(per_serv['sat_fat'], 1), 'sodium_mg': r(per_serv['sodium']),
            'cholesterol_mg': r(per_serv['cholesterol']),
            'calcium_mg': r(per_serv['calcium']), 'iron_mg': r(per_serv['iron'], 1),
            'potassium_mg': r(per_serv['potassium']), 'magnesium_mg': r(per_serv['magnesium']),
            'zinc_mg': r(per_serv['zinc'], 1), 'vit_a_ug': r(per_serv['vit_a_rae']),
            'vit_c_mg': r(per_serv['vit_c'], 1), 'vit_d_ug': r(per_serv['vit_d'], 1),
            'vit_e_mg': r(per_serv['vit_e'], 1), 'folate_ug': r(per_serv['folate']),
        },
        'per_100g': {k: round(v, 2) for k, v in per_100g.items() if v},
        'health_scores': {
            'nutri_score': ns,
            'nrf9_3': nrf,
            'nova_group': nova,
            'hei_2020': hei,
        },
        'cooking_method': method,
        'retention_applied': method != 'none',
        'coverage': {
            'matched_pct': round(coverage, 2),
            'estimate_quality': round(overall, 2),
            'confidence': confidence,
            'unmatched': sorted(set(unmatched))[:12],
            'servings_note': serv_note,
            'cure_note': cure_note,
        },
    }

def apply_corrections(out):
    """Apply human-in-the-loop overrides from data/manual_corrections.json (by id),
    last. Supports overriding `servings` (per-serving figures rescale from the total)
    and any per_serving field; records the correction + reason on the recipe."""
    path = os.path.join(DATA, 'manual_corrections.json')
    if not os.path.exists(path):
        return out
    corr = {k: v for k, v in json.load(open(path)).items() if not k.startswith('_')}
    by = {r['id']: r for r in out}
    for rid, fix in corr.items():
        r = by.get(rid)
        if not r:
            continue
        if 'servings' in fix and fix['servings']:
            old = r['servings']; new = fix['servings']
            r['servings'] = new
            if old:
                scale = old / new
                for k, v in r['per_serving'].items():
                    r['per_serving'][k] = round(v * scale, 1 if isinstance(v, float) else 0)
                unc = r['uncertainty_pct'] / 100
                r['kcal_range'] = [round(r['per_serving']['kcal'] * (1 - unc)),
                                   round(r['per_serving']['kcal'] * (1 + unc))]
        for k, v in fix.get('per_serving', {}).items():
            r['per_serving'][k] = v
        r['manual_correction'] = fix.get('note', 'manually corrected')
    return out

# ---------------------------------------------------------------------------
if __name__ == '__main__':
    recs = json.load(open(os.path.join(DATA, 'all_recipes.json')))['recipes']
    out = [analyze(r) for r in recs]
    out = apply_corrections(out)
    with open(os.path.join(DATA, 'recipe_nutrition.json'), 'w', encoding='utf-8') as fh:
        json.dump({'recipe_count': len(out),
                   'reference': 'nutrition_methodology_wiki.md',
                   'notes': 'Estimates (±10-25%). Cooking yield/retention factors not yet applied.',
                   'recipes': out}, fh, ensure_ascii=False, indent=2)

    # ---- Markdown report ----
    NS_EMOJI = {'A': '🟢', 'B': '🟢', 'C': '🟡', 'D': '🟠', 'E': '🔴'}
    CONF = {'high': '', 'medium': ' ⚠︎', 'low': ' ⚠︎⚠︎'}
    L = ['# Recipe Nutrition & Health\n',
         'Per-serving nutrition estimated from USDA FoodData Central, plus health scores. '
         'Method: `nutrition_methodology_wiki.md`. **Estimates (±10–25%);** a ⚠︎ marks '
         'medium/low match confidence. Cooking yield/retention factors are not yet applied.\n']
    hi = [r for r in out if r['coverage']['confidence'] == 'high']
    L.append(f'{len(out)} recipes · avg **{round(sum(r["per_serving"]["kcal"] for r in out)/len(out))} kcal/serving** · '
             f'{len(hi)} high-confidence.\n')
    L.append('## All recipes\n')
    L.append('| Recipe | kcal/serv | total kcal | Protein | Carb | Fat | Fiber | Sodium | Nutri-Score | NRF9.3 | NOVA | HEI | Cooked |')
    L.append('|---|--:|--:|--:|--:|--:|--:|--:|:--:|--:|:--:|--:|:--:|')
    for r in sorted(out, key=lambda x: x['name'].lower()):
        p = r['per_serving']; h = r['health_scores']; ns = h['nutri_score']['grade']
        hei = h['hei_2020']['total'] if h['hei_2020'] else '—'
        L.append(f"| {r['name']}{CONF[r['coverage']['confidence']]} | {p['kcal']} | {r['total_kcal']} | "
                 f"{p['protein_g']}g | {p['carb_g']}g | {p['fat_g']}g | {p['fiber_g']}g | {p['sodium_mg']}mg | "
                 f"{NS_EMOJI[ns]} {ns} | {h['nrf9_3']} | {h['nova_group']} | {hei} | {r['cooking_method']} |")
    with open(os.path.join(DATA, 'recipe_nutrition.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))

    from collections import Counter
    cov = Counter(r['coverage']['confidence'] for r in out)
    ns = Counter(r['health_scores']['nutri_score']['grade'] for r in out)
    print(f'Analyzed {len(out)} recipes')
    print('Coverage confidence:', dict(cov))
    print('Nutri-Score grades:', dict(sorted(ns.items())))
    med = sorted(out, key=lambda x: x['per_serving']['kcal'])
    print('avg kcal/serving:', round(sum(r["per_serving"]["kcal"] for r in out)/len(out)))
    print('sample:')
    for r in out[:5]:
        ps = r['per_serving']
        print(f"  {r['name'][:38]:38s} {ps['kcal']:4d} kcal  P{ps['protein_g']} C{ps['carb_g']} F{ps['fat_g']}  "
              f"NS={r['health_scores']['nutri_score']['grade']} NRF={r['health_scores']['nrf9_3']} "
              f"cov={r['coverage']['matched_pct']}")
