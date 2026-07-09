#!/usr/bin/env python3
"""Add a new recipe to the collection — it then gets scored across all dimensions.

Usage:
  python3 scripts/add_recipe.py --url https://example.com/some-recipe      # from a website
  python3 scripts/add_recipe.py --file my_recipe.txt                       # from a text file
  cat my_recipe.txt | python3 scripts/add_recipe.py                        # from a paste (stdin)
  add ... --rebuild                                                        # also regenerate everything

Recipes are stored in data/user_recipes.json (persists across re-parsing). After adding,
run  bash scripts/run_all.sh  (or pass --rebuild) to score the new recipe everywhere and
refresh the web app.

Text-file / paste format (flexible):
    Title: My Weeknight Curry
    Servings: 4
    Source: grandma
    Ingredients:
    - 1 lb chicken thighs
    - 1 can coconut milk
    Directions:
    1. Brown the chicken.
    2. Simmer with coconut milk 20 min.
"""
import os, re, sys, json, html, argparse, subprocess
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'data')
STORE = os.path.join(DATA, 'user_recipes.json')

def clean(s):
    if not s:
        return None
    s = html.unescape(re.sub(r'<[^>]+>', ' ', str(s)))
    return re.sub(r'\s+', ' ', s).strip() or None

# ---------- URL (schema.org / JSON-LD) ----------
def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (recipe-importer)'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', 'ignore')

def find_recipe_node(obj):
    """Walk JSON-LD to find the Recipe object."""
    if isinstance(obj, list):
        for o in obj:
            n = find_recipe_node(o)
            if n:
                return n
    elif isinstance(obj, dict):
        t = obj.get('@type')
        types = t if isinstance(t, list) else [t]
        if 'Recipe' in types:
            return obj
        if '@graph' in obj:
            return find_recipe_node(obj['@graph'])
    return None

def flatten_instructions(ins):
    out = []
    if isinstance(ins, str):
        return [clean(x) for x in re.split(r'(?<=[.!?])\s+|\n+', ins) if clean(x)]
    for step in ins or []:
        if isinstance(step, str):
            out.append(clean(step))
        elif isinstance(step, dict):
            if step.get('@type') == 'HowToSection':
                out += flatten_instructions(step.get('itemListElement', []))
            else:
                out.append(clean(step.get('text') or step.get('name')))
    return [s for s in out if s]

def nutrition_str(n):
    if not isinstance(n, dict):
        return None
    m = {'calories': 'Calories', 'proteinContent': 'Protein', 'carbohydrateContent': 'Carbohydrates',
         'fatContent': 'Fat', 'saturatedFatContent': 'Saturated Fat', 'fiberContent': 'Fiber',
         'sugarContent': 'Sugar', 'sodiumContent': 'Sodium'}
    parts = [f'{lbl}: {clean(n[k])}' for k, lbl in m.items() if n.get(k)]
    return ' | '.join(parts) or None

def from_url(url):
    doc = fetch(url)
    node = None
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', doc, re.S | re.I):
        try:
            node = find_recipe_node(json.loads(m.group(1)))
        except Exception:
            continue
        if node:
            break
    if not node:
        sys.exit('Could not find recipe data (schema.org/Recipe) on that page. '
                 'Try saving it as a text file and using --file instead.')
    y = node.get('recipeYield')
    if isinstance(y, list):
        y = y[0] if y else None
    author = node.get('author')
    if isinstance(author, dict):
        author = author.get('name')
    elif isinstance(author, list) and author:
        author = author[0].get('name') if isinstance(author[0], dict) else author[0]
    cats = node.get('recipeCategory') or []
    if isinstance(cats, str):
        cats = [cats]
    return {
        'name': clean(node.get('name')) or 'Untitled recipe',
        'ingredients': [clean(x) for x in (node.get('recipeIngredient') or node.get('ingredients') or []) if clean(x)],
        'directions': flatten_instructions(node.get('recipeInstructions')),
        'servings': clean(str(y)) if y else None,
        'source': clean(author) or urllib.parse.urlparse(url).netloc,
        'source_url': url,
        'categories': [clean(c) for c in cats if clean(c)],
        'description': clean(node.get('description')),
        'nutrition': nutrition_str(node.get('nutrition')),
        'prep_time': None, 'cook_time': None, 'total_time': None, 'difficulty': None, 'notes': None,
    }

# ---------- text / paste ----------
def from_text(text):
    lines = text.splitlines()
    title = source = servings = None
    ings, dirs = [], []
    mode = None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        m = re.match(r'(title|name|servings?|serves|yield|source)\s*[:\-]\s*(.+)', s, re.I)
        if m and mode is None:
            key, val = m.group(1).lower(), m.group(2).strip()
            if key in ('title', 'name'): title = val
            elif key == 'source': source = val
            else: servings = val
            continue
        if re.match(r'ingredients?\s*[:\-]?\s*$', low):
            mode = 'ing'; continue
        if re.match(r'(directions?|instructions?|method|steps?)\s*[:\-]?\s*$', low):
            mode = 'dir'; continue
        if title is None and mode is None:
            title = s; continue
        item = re.sub(r'^[\-\*•\d]+[\.\)]?\s*', '', s)
        if mode == 'ing': ings.append(item)
        elif mode == 'dir': dirs.append(item)
    if not title or not ings:
        sys.exit('Could not parse a title + ingredients. Use the format shown in --help.')
    return {'name': title, 'ingredients': ings, 'directions': dirs, 'servings': servings,
            'source': source, 'source_url': None, 'categories': [], 'description': None,
            'nutrition': None, 'prep_time': None, 'cook_time': None, 'total_time': None,
            'difficulty': None, 'notes': None}

# ---------- store ----------
def add(rec):
    store = json.load(open(STORE)) if os.path.exists(STORE) else {'recipes': []}
    existing = store['recipes']
    key = (rec.get('source_url'), rec['name'].lower())
    existing[:] = [r for r in existing if (r.get('source_url'), r['name'].lower()) != key]  # replace dup
    existing.append(rec)
    json.dump(store, open(STORE, 'w'), ensure_ascii=False, indent=2)
    return len(existing)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Add a recipe to the collection.')
    ap.add_argument('--url'); ap.add_argument('--file'); ap.add_argument('--rebuild', action='store_true')
    a = ap.parse_args()
    if a.url:
        rec = from_url(a.url)
    elif a.file:
        rec = from_text(open(a.file, encoding='utf-8').read())
    else:
        if sys.stdin.isatty():
            sys.exit('Provide --url, --file, or pipe recipe text via stdin. See --help.')
        rec = from_text(sys.stdin.read())

    n = add(rec)
    print(f'✓ Added "{rec["name"]}" — {len(rec["ingredients"])} ingredients, '
          f'{len(rec["directions"])} steps, servings={rec.get("servings")!r}')
    print(f'  Stored in data/user_recipes.json ({n} user recipe(s) total).')
    if a.rebuild:
        print('  Rebuilding pipeline…')
        subprocess.run(['bash', os.path.join(REPO, 'scripts', 'run_all.sh')], check=True)
    else:
        print('  Next: run  bash scripts/run_all.sh  to score it everywhere and refresh the app.')
