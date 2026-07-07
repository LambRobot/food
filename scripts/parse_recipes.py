#!/usr/bin/env python3
"""Parse Paprika HTML recipe exports into a single JSON + Markdown document."""
import re, glob, os, json, html, unicodedata

# Paths are relative to the repo root (parent of this scripts/ directory).
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "source", "paprika-export", "Recipes")
OUT_DIR = os.path.join(REPO, "data")
os.makedirs(OUT_DIR, exist_ok=True)

def clean(text):
    """Unescape HTML entities and collapse whitespace on a single string."""
    if text is None:
        return None
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text or None

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s)

def get_single(s, itemprop):
    """Extract text content of a single element with the given itemprop."""
    m = re.search(r'itemprop="%s"[^>]*>(.*?)</' % itemprop, s, re.S)
    if not m:
        return None
    return clean(strip_tags(m.group(1)))

def get_lines(s, box_class, itemprop):
    """Extract a list of text lines from a labelled box.

    Ingredients tag each <p> with the itemprop; directions wrap all <p>s in
    one div carrying the itemprop. Handle both by isolating the box via its
    '<class> text' div, then pulling every <p> inside it.
    """
    m = re.search(r'<div[^>]*class="%s text"[^>]*>(.*?)</div>' % box_class, s, re.S)
    if not m:
        return []
    inner = m.group(1)
    parts = re.findall(r'<p[^>]*>(.*?)</p>', inner, re.S)
    if not parts:
        parts = [inner]
    out = []
    for p in parts:
        c = clean(strip_tags(p))
        if c:
            out.append(c)
    return out

def get_metadata(s, label):
    """Extract metadata like Prep Time / Cook Time by its bold label."""
    m = re.search(r'<b>%s:\s*</b><span[^>]*>(.*?)</span>' % re.escape(label), s, re.S)
    return clean(m.group(1)) if m else None

def parse_file(path):
    s = open(path, encoding='utf-8').read()
    r = {}
    r['name'] = get_single(s, 'name') or clean(os.path.splitext(os.path.basename(path))[0])

    # categories
    m = re.search(r'<p[^>]*class="categories"[^>]*>(.*?)</p>', s, re.S)
    cats = clean(strip_tags(m.group(1))) if m else None
    r['categories'] = [c.strip() for c in re.split(r',', cats)] if cats else []

    r['prep_time'] = get_metadata(s, 'Prep Time')
    r['cook_time'] = get_metadata(s, 'Cook Time')
    r['total_time'] = get_metadata(s, 'Total Time')
    r['servings'] = get_metadata(s, 'Servings')
    r['difficulty'] = get_metadata(s, 'Difficulty')

    # source
    author = get_single(s, 'author')
    m = re.search(r'itemprop="url"\s+href="([^"]*)"', s)
    source_url = m.group(1) if m else None
    r['source'] = author
    r['source_url'] = source_url

    r['description'] = get_single(s, 'description')
    r['ingredients'] = get_lines(s, 'ingredients', 'recipeIngredient')
    r['directions'] = get_lines(s, 'directions', 'recipeInstructions')
    r['notes'] = get_single(s, 'comment')
    r['nutrition'] = get_single(s, 'nutrition')
    return r

files = sorted(glob.glob(os.path.join(SRC, '*.html')))
recipes = [parse_file(f) for f in files]
recipes.sort(key=lambda x: (x['name'] or '').lower())

# ---- JSON ----
json_path = os.path.join(OUT_DIR, 'all_recipes.json')
with open(json_path, 'w', encoding='utf-8') as fh:
    json.dump({'recipe_count': len(recipes), 'recipes': recipes},
              fh, ensure_ascii=False, indent=2)

# ---- Markdown ----
def md_recipe(r):
    lines = []
    lines.append('## %s' % r['name'])
    lines.append('')
    meta = []
    if r['categories']: meta.append('**Categories:** ' + ', '.join(r['categories']))
    if r['servings']: meta.append('**Servings:** ' + r['servings'])
    if r['prep_time']: meta.append('**Prep:** ' + r['prep_time'])
    if r['cook_time']: meta.append('**Cook:** ' + r['cook_time'])
    if r['total_time']: meta.append('**Total:** ' + r['total_time'])
    if r['difficulty']: meta.append('**Difficulty:** ' + r['difficulty'])
    if r['source']:
        src = r['source']
        if r['source_url']:
            src = '[%s](%s)' % (r['source'], r['source_url'])
        meta.append('**Source:** ' + src)
    elif r['source_url']:
        meta.append('**Source:** ' + r['source_url'])
    if meta:
        lines.append('  \n'.join(meta))
        lines.append('')
    if r['description']:
        lines.append('_%s_' % r['description'])
        lines.append('')
    if r['ingredients']:
        lines.append('### Ingredients')
        for i in r['ingredients']:
            lines.append('- ' + i)
        lines.append('')
    if r['directions']:
        lines.append('### Directions')
        for n, d in enumerate(r['directions'], 1):
            lines.append('%d. %s' % (n, d))
        lines.append('')
    if r['notes']:
        lines.append('### Notes')
        lines.append(r['notes'])
        lines.append('')
    if r['nutrition']:
        lines.append('### Nutrition')
        lines.append(r['nutrition'])
        lines.append('')
    return '\n'.join(lines)

md_path = os.path.join(OUT_DIR, 'all_recipes.md')
with open(md_path, 'w', encoding='utf-8') as fh:
    fh.write('# Recipe Collection\n\n')
    fh.write('Compiled from Paprika export. %d recipes.\n\n' % len(recipes))
    # table of contents
    fh.write('## Index\n\n')
    for r in recipes:
        anchor = r['name']
        fh.write('- %s\n' % anchor)
    fh.write('\n---\n\n')
    for r in recipes:
        fh.write(md_recipe(r))
        fh.write('\n---\n\n')

# ---- stats ----
missing_ing = sum(1 for r in recipes if not r['ingredients'])
missing_dir = sum(1 for r in recipes if not r['directions'])
print('Recipes parsed:', len(recipes))
print('Missing ingredients:', missing_ing)
print('Missing directions:', missing_dir)
print('JSON:', json_path, os.path.getsize(json_path), 'bytes')
print('MD  :', md_path, os.path.getsize(md_path), 'bytes')
if missing_ing:
    print('  no-ingredient files:', [r['name'] for r in recipes if not r['ingredients']][:20])
