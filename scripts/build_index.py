#!/usr/bin/env python3
"""Build the canonical recipe index — the join table for all per-recipe data.

Reads the parsed recipes and the Mediterranean scores, derives a transparent
cuisine + dish-type guess, and emits data/index.json + data/index.md. Future
dimensions (nutrition, allergens, cost, ...) should be per-recipe files keyed by
`id`; add the filename to DIMENSIONS below so the index advertises it.
"""
import os, re, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'data')

# Per-recipe data files that are keyed by `id` (join on it).
DIMENSIONS = {
    'mediterranean_score': 'recipe_mediterranean_scores.json',
    'mediterranean_improvement': 'recipe_improvements.json',
    'nutrition': 'recipe_nutrition.json',
    'fatty_liver': 'recipe_fatty_liver.json',
}

# ---- cuisine guess: check categories first, then name, then ingredients ----
# Ordered so more specific cuisines win over generic "Asian".
CUISINE_KW = [
    ('Mexican',        ['mexican','taco','enchilada','guacamole','salsa','pozole','carne asada','tortilla','queso','chili con','tomatillo','mole','fajita']),
    ('Italian',        ['italian','pasta','risotto','carbonara','pesto','parmigiana','osso buco','ragu','ragù','gnocchi','bolognese','alfredo','ziti','lasagn','marinara','genovese']),
    ('Indian',         ['indian','curry','masala','biryani','dal','dahl','tikka','korma','paneer','tandoori','garam','aloo','gobi','momo','kachumber','chutney']),
    ('Thai',           ['thai','pad thai','pad see','panang','tom yum','green curry','red curry','lemongrass','massaman','khao']),
    ('Vietnamese',     ['vietnamese','pho','banh mi','bánh','goi','nuoc','sinigang']),
    ('Japanese',       ['japanese','ramen','sushi','miso','teriyaki','katsu','karaage','tonkatsu','tonkotsu','gyudon','japchae','soba','sunomono','poke','chashu','izakaya','yakitori']),
    ('Korean',         ['korean','kimchi','bibimbap','bulgogi','gochujang','japchae']),
    ('Chinese',        ['chinese','stir-fry','stir fry','mongolian','general tso','potsticker','siu mai','hoisin','szechuan','sichuan','wonton','dumpling','fried rice','chow']),
    ('Moroccan/N.African',['moroccan','tagine','harira','ras el','preserved lemon','chermoula','winter tagine','harissa']),
    ('Middle Eastern', ['middle eastern','shakshuka','hummus','baba ganoush','falafel','tahini','couscous','za\'atar','shawarma','kofta','labneh','fattoush']),
    ('Greek',          ['greek','moussaka','tzatziki','souvlaki','spanakopita','gyro','feta','avgolemono']),
    ('French',         ['french','coq au vin','béchamel','bechamel','gratin','ratatouille','cassoulet','provenc','normande','frangipane','galette','financier','madeleine','beurre','crème','creme','parmentier','rillettes','choucroute','veau','bourgu']),
    ('Belgian',        ['belg','waterzooi','liég','liege','frites à la belge','cougnou','matoufé','stoemp','mutzen','boulet']),
    ('German',         ['german','kartoffel','streusel','currywurst','kasseler','berliner','joghurt keks','brötchen','brotchen','schnitzel','spätzle']),
    ('Spanish',        ['spanish','paella','gazpacho','tapas','chorizo','tortilla espa','patatas']),
    ('Portuguese',     ['portuguese','caldo verde','bacalhau','piri','favas','caldeirada','portugu']),
    ('Cajun/Creole',   ['cajun','creole','gumbo','jambalaya','étouffée','etouffee','andouille','maque choux','remoulade','mirliton']),
    ('Caribbean',      ['jamaican','jerk','caribbean','plantain','cuban']),
    ('British/Irish',  ['british','english','irish','shepherd','cornish pasty','cottage pie','bangers','guinness','pasty']),
    ('American',       ['american','bbq','barbecue','brisket','cobb','mac and cheese','meatloaf','buffalo','cornbread','pot pie','deviled','ranch','smoked','tri tip','tri-tip']),
    ('Afghan',         ['afghan','shorwa']),
    ('Filipino',       ['filipino','sinigang','adobo','lumpia']),
    ('Laotian',        ['lao','larb']),
]

# ---- dish type ----
def dish_type(name, cats, is_dessert):
    n = name.lower(); c = ' '.join(cats).lower()
    def hit(*ws): return any(w in n or w in c for w in ws)
    if is_dessert or hit('cake','cookie','ice cream','pie','tart','brownie','cupcake','pudding','mousse',
                          'cheesecake','scone','muffin','pavlova','dessert','frangipane','custard','pops'):
        return 'dessert'
    if hit('cocktail','margarita','smoothie','juice','drink','pops'):
        return 'drink'
    if hit('bread','focaccia','sourdough','baguette','brioche','scone','rolls','buns','loaf','naan','pão','pao'):
        return 'bread/baked'
    if hit('salad','slaw','kachumber'):
        return 'salad'
    if hit('soup','stew','broth','chowder','bisque','gumbo','ramen','pho','caldo'):
        return 'soup/stew'
    if hit('sauce','dressing','marinade','pesto','ketchup','mayo','salsa','dip','chutney','nappage','vinaigrette','béchamel','bechamel','curry paste'):
        return 'sauce/condiment'
    if hit('rice','quinoa','couscous','beans','potato','vegetable','veggie','greens','side','pickle','broccolini','favas','gratin','stoemp'):
        return 'side'
    if hit('breakfast','pancake','waffle','oatmeal','granola','egg','omelet','scramble','shakshuka','porridge'):
        return 'breakfast'
    return 'main'

def guess_cuisine(name, cats, ings):
    hay_cat = ' '.join(cats).lower()
    hay_name = name.lower()
    hay_ing = ' '.join(ings).lower()
    for source, hay in (('category', hay_cat), ('name', hay_name), ('ingredients', hay_ing)):
        for cuisine, kws in CUISINE_KW:
            if any(k in hay for k in kws):
                return cuisine, source
    return 'Unspecified', None

# ---------------------------------------------------------------------------
recs = json.load(open(os.path.join(DATA, 'all_recipes.json')))['recipes']
scores = {r['id']: r for r in json.load(open(os.path.join(DATA, DIMENSIONS['mediterranean_score'])))['recipes']}
_nutf = os.path.join(DATA, DIMENSIONS.get('nutrition', ''))
nutrition = {r['id']: r for r in json.load(open(_nutf))['recipes']} if os.path.exists(_nutf) else {}
_flf = os.path.join(DATA, DIMENSIONS.get('fatty_liver', ''))
fatty = {r['id']: r for r in json.load(open(_flf))['recipes']} if os.path.exists(_flf) else {}

index = []
for r in recs:
    sc = scores.get(r['id'], {})
    cuisine, csource = guess_cuisine(r['name'], r.get('categories') or [], r['ingredients'])
    index.append({
        'id': r['id'],
        'name': r['name'],
        'cuisine': cuisine,
        'cuisine_source': csource,          # category | name | ingredients | None (=guess confidence)
        'dish_type': dish_type(r['name'], r.get('categories') or [], sc.get('is_dessert')),
        'categories': r.get('categories') or [],
        'servings': r.get('servings'),
        'total_time': r.get('total_time'),
        'source': r.get('source'),
        'flags': {
            'non_food': bool(r.get('non_food')),
            'out_of_scope': bool(r.get('out_of_scope')),
            'out_of_scope_reason': r.get('out_of_scope_reason'),
            'duplicate_of': r.get('duplicate_of'),
            'is_dessert': bool(sc.get('is_dessert')),
        },
        'mediterranean': {'score': sc.get('score'), 'grade': sc.get('grade')},
        'nutrition': (lambda nu: {
            'kcal': nu['per_serving']['kcal'],
            'total_kcal': nu.get('total_kcal'),
            'nutri_score': nu['health_scores']['nutri_score']['grade'],
            'nova_group': nu['health_scores']['nova_group'],
            'confidence': nu['coverage']['confidence'],
        } if nu else None)(nutrition.get(r['id'])),
        'fatty_liver': (lambda fl: {'score': fl['score'], 'grade': fl['grade']}
                        if fl else None)(fatty.get(r['id'])),
    })

index.sort(key=lambda x: x['name'].lower())

with open(os.path.join(DATA, 'index.json'), 'w', encoding='utf-8') as fh:
    json.dump({
        'recipe_count': len(index),
        'description': 'Canonical join table. Join per-recipe data on `id`.',
        'dimensions': {k: {'file': v, 'key': 'id'} for k, v in DIMENSIONS.items()},
        'recipes': index,
    }, fh, ensure_ascii=False, indent=2)

# ---- Markdown ----
from collections import Counter
cz = Counter(r['cuisine'] for r in index)
dz = Counter(r['dish_type'] for r in index)
L = ['# Recipe Index\n',
     'Canonical join table for the collection. Every per-recipe data file is keyed by **`id`** — '
     'join on it to attach new dimensions.\n',
     f'**{len(index)} recipes.**\n',
     '## Available data dimensions (join on `id`)\n',
     '| Dimension | File |', '|---|---|']
for k, v in DIMENSIONS.items():
    L.append(f'| {k} | `data/{v}` |')
L += ['', '## Cuisine breakdown\n', '| Cuisine | Count |', '|---|---|']
for c, n in cz.most_common():
    L.append(f'| {c} | {n} |')
L += ['', '## Dish-type breakdown\n', '| Type | Count |', '|---|---|']
for t, n in dz.most_common():
    L.append(f'| {t} | {n} |')
L += ['', '## Full index\n',
      '| id | Recipe | Cuisine | Type | Med score | Flags |', '|---|---|---|---|---|---|']
for r in index:
    flags = []
    if r['flags']['non_food']: flags.append('non-food')
    if r['flags']['duplicate_of']: flags.append('dup')
    if r['flags']['is_dessert']: flags.append('dessert')
    med = f"{r['mediterranean']['score']} ({r['mediterranean']['grade']})" if r['mediterranean']['score'] is not None else '—'
    cui = r['cuisine'] + ('' if r['cuisine_source'] == 'category' else '?')  # '?' = guessed, not from a category tag
    L.append(f"| `{r['id']}` | {r['name']} | {cui} | {r['dish_type']} | {med} | {', '.join(flags)} |")

with open(os.path.join(DATA, 'index.md'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(L))

print(f'Indexed {len(index)} recipes')
print('Cuisines:', dict(cz.most_common(8)))
print('Dish types:', dict(dz.most_common()))
print('Cuisine from explicit category:', sum(1 for r in index if r['cuisine_source'] == 'category'),
      '| guessed:', sum(1 for r in index if r['cuisine'] != 'Unspecified' and r['cuisine_source'] != 'category'),
      '| unspecified:', sum(1 for r in index if r['cuisine'] == 'Unspecified'))
