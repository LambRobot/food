#!/usr/bin/env python3
"""Ingredient -> USDA food matcher (the accuracy-critical step), with an audit mode.

Heuristic scorer that exploits USDA's "HEAD, modifier, modifier" description format,
prefers raw/basic whole foods over branded/prepared items, plus a curated override
map for common/ambiguous ingredients. Run directly to audit match quality over the
whole collection's ingredient vocabulary.
"""
import os, re, json, sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'data')

_ref = None
def ref():
    global _ref
    if _ref is None:
        _ref = json.load(open(os.path.join(DATA, 'usda_reference.json')))['foods']
    return _ref

# curated overrides: normalized ingredient -> exact USDA fdc_id (fills matcher gaps)
OVERRIDES = json.load(open(os.path.join(DATA, 'ingredient_overrides.json'))) \
    if os.path.exists(os.path.join(DATA, 'ingredient_overrides.json')) else {}

PREP = set('chopped sliced minced diced fresh dried ground large medium small about more '
           'taste finely thinly plus optional see note homemade store bought room temperature '
           'roughly crushed peeled rinsed drained cooked raw halved quartered cut into pieces '
           'thick thin whole boneless skinless freshly grated shredded softened melted cold warm '
           'ripe firm packed level heaping trimmed cored seeded stemmed toasted'.split())
# measurement / container words are not part of the food name
UNITS = set('cup cups tablespoon tablespoons tbsp teaspoon teaspoons tsp gram grams kg kilogram '
            'ml milliliter liter litre oz ounce ounces lb lbs pound pounds pinch dash handful '
            'clove cloves can cans slice slices stick sticks sprig sprigs bunch bunches package '
            'packages quart quarts pint pints piece pieces jar jars box head heads stalk stalks '
            'fillet fillets strip strips cube cubes cl dl'.split())
# French/German -> English so matches hit USDA (English DB)
XLATE = {'oignon': 'onion', 'ail': 'garlic', 'beurre': 'butter', 'farine': 'flour', 'lait': 'milk',
         'oeuf': 'egg', 'oeufs': 'egg', 'sucre': 'sugar', 'crème': 'cream', 'creme': 'cream',
         'poulet': 'chicken', 'boeuf': 'beef', 'porc': 'pork', 'jambon': 'ham', 'saumon': 'salmon',
         'thon': 'tuna', 'crevette': 'shrimp', 'poisson': 'fish', 'pomme de terre': 'potato',
         'champignon': 'mushroom', 'poireau': 'leek', 'épinard': 'spinach', 'carotte': 'carrot',
         'tomate': 'tomato', 'fromage': 'cheese', 'zwiebel': 'onion', 'kartoffel': 'potato',
         'mehl': 'flour', 'zucker': 'sugar', 'sahne': 'cream', 'knoblauch': 'garlic'}

def singular(w):
    if w.endswith('oes'): return w[:-2]
    if w.endswith('ies'): return w[:-3] + 'y'
    if w.endswith('s') and not w.endswith('ss'): return w[:-1]
    return w

QUALIFIER = re.compile(r'\b(low[- ]sodium|reduced[- ]sodium|no salt added|low[- ]fat|reduced[- ]fat|'
                       r'fat[- ]free|part[- ]skim|light|lite|unsalted|salted|organic|free[- ]range)\b')

def normalize(name):
    n = name.lower()
    n = re.sub(r'\([^)]*\)', ' ', n)                 # drop parentheticals
    n = n.split(',')[0]                               # keep head phrase before comma
    n = QUALIFIER.sub(' ', n)                         # strip label qualifiers so overrides hit
    for fr, en in XLATE.items():
        n = re.sub(r'(?<![a-z])' + re.escape(fr) + r'(?![a-z])', en, n)
    words = [w for w in re.findall(r"[a-zà-ÿ']+", n) if w not in PREP and w not in UNITS and len(w) > 1]
    words = [singular(w) for w in words]
    return words

BAD_DESC = ['reduced', 'low fat', 'lowfat', 'nonfat', 'fat free', 'with ', 'canned', 'infant',
            'baby food', 'flavored', 'imitation', 'substitute', 'from concentrate', 'dehydrated',
            'condensed', 'dry mix', 'powder', 'sauce,', 'soup,', 'candies', 'snack', 'fast food',
            'restaurant', 'school', 'nfs', 'not further specified',
            'skin only', ', skin', 'giblet', 'neck', 'back,', 'separable fat', 'ground, raw',
            'extender', 'meatless', 'substitute', 'wurst', 'salami', 'bologna', 'luncheon',
            'cured', 'corned', 'analog']

def score(qtokens, food):
    desc = food['desc'].lower()
    dtoks = set(re.findall(r"[a-z']+", desc))
    head = singular(desc.split(',')[0].strip().split()[0]) if desc else ''
    qset = set(qtokens)
    overlap = len(qset & {singular(t) for t in dtoks})
    if overlap == 0:
        return -99
    s = overlap * 3
    if head in qset:
        s += 8                                       # USDA head noun matches the ingredient
    if qtokens and singular(qtokens[-1]) == head:
        s += 3
    if 'raw' in dtoks: s += 2
    if {'cooked', 'boiled', 'roasted', 'baked'} & dtoks: s += 1
    if food['type'] == 'sr_legacy_food': s += 1
    for b in BAD_DESC:
        if b in desc: s -= 3
    s -= 0.03 * len(desc)                            # prefer concise/canonical
    if 'kcal' not in food['n']: s -= 6
    # bonus: all query tokens present
    if qset <= {singular(t) for t in dtoks}: s += 4
    return s

# leading adjectives that can be dropped to reach an override (NB: 'sweet' excluded
# so "sweet potato" never collapses to "potato")
LEAD_ADJ = {'red', 'yellow', 'green', 'white', 'large', 'medium', 'small', 'baby', 'fresh',
            'dried', 'whole', 'lean', 'boneless', 'skinless', 'ripe', 'organic', 'light', 'dark',
            'hot', 'ground', 'minced', 'extra', 'virgin', 'raw', 'plain', 'purple', 'golden'}

def match(name):
    """Return (fdc_id, food, confidence) or (None, None, 0)."""
    tokens = normalize(name)
    if not tokens:
        return None, None, 0.0
    key = ' '.join(tokens)
    # try the full key, then with leading adjectives stripped ("red kidney bean"->"kidney bean")
    cand = [key]
    t = tokens[:]
    while t and t[0] in LEAD_ADJ:
        t = t[1:]
        if t:
            cand.append(' '.join(t))
    for c in cand:
        if c in OVERRIDES:
            fid = str(OVERRIDES[c])
            if fid in ref():
                return fid, ref()[fid], 1.0
    best, best_s = None, -1
    for fid, food in ref().items():
        sc = score(tokens, food)
        if sc > best_s:
            best_s, best = sc, (fid, food)
    if best is None or best_s < 4:
        return None, None, 0.0
    conf = max(0.3, min(0.95, best_s / 20))
    return best[0], best[1], round(conf, 2)

# ---------------------------------------------------------------------------
if __name__ == '__main__':
    recs = json.load(open(os.path.join(DATA, 'all_recipes.json')))['recipes']
    # collect unique normalized ingredient heads with frequency
    freq = Counter()
    examples = {}
    for r in recs:
        for ing in r['ingredients']:
            key = ' '.join(normalize(ing))
            if key:
                freq[key] += 1
                examples.setdefault(key, ing)
    print(f'{len(freq)} distinct normalized ingredients; showing the {sys.argv[1] if len(sys.argv)>1 else 60} most common\n')
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    matched = unmatched = 0
    for key, n in freq.most_common(N):
        fid, food, conf = match(key)
        if food:
            matched += 1
            print(f'{n:3d}x  {key:28s} -> [{conf:.2f}] {food["desc"][:52]}')
        else:
            unmatched += 1
            print(f'{n:3d}x  {key:28s} -> ??? UNMATCHED  (e.g. "{examples[key][:40]}")')
    # full-vocab coverage
    fm = sum(1 for k in freq if match(k)[1])
    print(f'\nTop-{N}: {matched} matched / {unmatched} unmatched')
    print(f'Full vocab: {fm}/{len(freq)} matched ({100*fm/len(freq):.0f}%)  |  '
          f'by frequency: {sum(freq[k] for k in freq if match(k)[1])}/{sum(freq.values())} lines')
