#!/usr/bin/env python3
"""Score every recipe for Mediterranean-diet fit.

Implements mediterranean_scoring_system.md: an ingredient rules-engine that tags
each ingredient good/bad with a severity measure, computes a 0-100 score + grade,
and emits comments and concrete swap suggestions.
"""
import json, re, os

# Paths are relative to the repo root (parent of this scripts/ directory).
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "data", "all_recipes.json")
OUT_DIR = os.path.join(REPO, "data")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def has(line, *words):
    """True if any whole-word term appears in line (matches optional trailing 's')."""
    for w in words:
        if re.search(r'(?<![a-z])' + re.escape(w) + r's?(?![a-z])', line):
            return True
    return False

_KEEP_PLURAL = {'brussels','asparagus','hummus','couscous','watercress','molasses','chickpeas'}
def canon(w):
    """Collapse a plural ingredient label to a singular display form."""
    if w in _KEEP_PLURAL:
        return w
    if w.endswith('oes'):   # tomatoes -> tomato, potatoes -> potato
        return w[:-2]
    if w.endswith('ies'):   # berries -> berry, cherries -> cherry
        return w[:-3] + 'y'
    if w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w

def amount_factor(line):
    """Scale a penalty by how much of the ingredient is used (condiment leniency)."""
    l = line
    # large amounts
    if re.search(r'(?<![a-z])(cup|cups|pound|pounds|lb|lbs|kg|kilo|quart|liter|litre)(?![a-z])', l):
        return 1.25
    m = re.search(r'(\d+)\s*g(?:ram)?s?(?![a-z])', l)
    if m and int(m.group(1)) >= 400:
        return 1.25
    # small / condiment amounts
    if re.search(r'(?<![a-z])(pinch|to taste|for garnish|garnish|splash|drizzle|for serving|dash)(?![a-z])', l):
        return 0.5
    if re.search(r'(?<![a-z])(1|one|½|1/2|a)\s+(tsp|teaspoon|tbsp|tablespoon|clove|cloves|slice|slices|strip|strips|sprig)', l):
        return 0.5
    if re.search(r'^\s*(1|one|½|1/2)\s+(tbsp|tablespoon|tsp|teaspoon)', l):
        return 0.5
    return 1.0

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
VEG = ['tomato','tomatoes','onion','onions','shallot','shallots','scallion','scallions',
       'leek','leeks','celery','carrot','carrots','mushroom','mushrooms','spinach','kale',
       'broccoli','broccolini','cauliflower','zucchini','courgette','eggplant','aubergine',
       'bell pepper','capsicum','cucumber','lettuce','cabbage','fennel','artichoke','artichokes',
       'asparagus','green bean','green beans','squash','butternut','pumpkin','beet','beets',
       'chard','arugula','rocket','okra','brussels','turnip','parsnip','celeriac','celery root',
       'chayote','mirliton','tomatillo','sweet potato','sweet potatoes','pea shoots','watercress',
       'radish','collard','endive','cipollini','plantain','poblano','jalapeno','jalapeño',
       'sprouts','bok choy','snow pea','snap pea','corn','sweetcorn',
       # multilingual (fr/de)
       'oignon','tomate','carotte','champignon','poireau','épinard','epinard','chou','céleri',
       'celeri','zwiebel','möhre','mohre','courgette','aubergine','fenouil']
AROMATIC = ['garlic','ginger','parsley','cilantro','coriander','basil','thyme','rosemary','oregano',
            'mint','dill','sage','bay leaf','bay leaves','cumin','paprika','turmeric','cinnamon',
            'cayenne','garam masala','curry','saffron','nutmeg','cardamom','cloves','fennel seed',
            'za\'atar','sumac','chives','tarragon','marjoram','coriander seed','mustard seed',
            'herbs','spice','spices','chili flakes','chile','chili powder','lemongrass','galangal',
            'persil','basilic','thym','romarin','knoblauch','muscade','safran']
LEGUME = ['lentil','lentils','chickpea','chickpeas','garbanzo','hummus','fava','edamame','dal','dahl',
          'black bean','black beans','kidney bean','kidney beans','cannellini','white bean','white beans',
          'pinto','navy bean','black-eyed pea','black eyed pea','split pea','refried beans','butter bean',
          'butter beans','borlotti','lima bean','lentille','lentilles','pois chiche','pois chiches',
          'haricot blanc','haricots blancs','linsen','kichererbsen']
WHOLEGRAIN = ['brown rice','wild rice','quinoa','bulgur','farro','barley','oats','oat','oatmeal',
              'rolled oats','whole wheat','whole-wheat','wholewheat','whole grain','whole-grain',
              'buckwheat','millet','spelt','freekeh','whole wheat pasta','whole wheat bread',
              'whole wheat flour','steel-cut','wheat berries']
OILY_FISH = ['salmon','sardine','sardines','mackerel','anchovy','anchovies','tuna','trout','herring',
             'saumon','thon','maquereau']
FISH_SEAFOOD = ['cod','tilapia','halibut','sole','sea bass','bass','snapper','haddock','pollock',
                'shrimp','prawn','prawns','squid','calamari','octopus','mussel','mussels','clam','clams',
                'oyster','oysters','scallop','scallops','crab','lobster','fish','seafood','poke','pollack',
                'cabillaud','crevette','moules','poisson','fisch']
NUTS = ['walnut','walnuts','almond','almonds','pistachio','pistachios','pine nut','pine nuts','pecan',
        'pecans','cashew','cashews','hazelnut','hazelnuts','peanut','peanuts','tahini','sesame seed',
        'sesame seeds','sunflower seed','pumpkin seed','chia','flax','flaxseed','poppy seed','poppy seeds']
FRUIT = ['lemon','lime','orange','apple','apples','pear','pears','grape','grapes','fig','figs','date',
         'dates','raisin','raisins','apricot','apricots','peach','peaches','plum','plums','cherry',
         'cherries','berry','berries','strawberry','strawberries','blueberry','blueberries','raspberry',
         'banana','bananas','mango','pineapple','pomegranate','melon','watermelon','currant','currants',
         'cranberry','cranberries','prune','prunes','kiwi','clementine','grapefruit']
DAIRY_GOOD = ['yogurt','yoghurt','feta','parmesan','parmigiano','ricotta','mozzarella','goat cheese',
              'halloumi','pecorino','cottage cheese','greek yogurt']
GOOD_EXTRA = ['olive','olives','avocado','capers','tomato paste']  # minor good markers

PROCESSED_MEAT = ['bacon','ham','prosciutto','pancetta','guanciale','sausage','sausages','salami',
                  'chorizo','pepperoni','hot dog','hot dogs','frankfurter','andouille','lardon','lardons',
                  'kielbasa','bratwurst','deli meat','cured','salt pork','mortadella','capicola','speck',
                  'smoked pork','cocktail sausage','saucisse','saucisson','kasseler','boudin',
                  # multilingual
                  'jambon','wurst','schinken','chipolata','lard fumé','lard fume',
                  'poitrine fumée','poitrine fumee','lardon fumé']
RED_MEAT = ['beef','steak','pork','lamb','veal','mutton','oxtail','brisket','sirloin','chuck','tri tip',
            'tri-tip','ground beef','ground pork','minced beef','short rib','short ribs','pork shoulder',
            'pork belly','pork loin','ribeye','flank','skirt steak','ground lamb','carne',
            'ground meat','minced meat','ground chuck','ground round','mince',
            # multilingual
            'boeuf','bœuf','porc','veau','agneau','viande','rind','schwein','hackfleisch','kalb',
            'viande hachée','viande hachee','bœuf haché','boeuf haché','boeuf hache','côte de veau','cote de veau']
BUTTER_CREAM = None  # handled by function
TROPICAL = ['coconut oil','coconut milk','coconut cream','creamed coconut','palm oil','coconut']
SUGAR_SEVERE = ['sweetened condensed milk','condensed milk','corn syrup']
SUGAR_MOD = ['sugar','brown sugar','powdered sugar','confectioners','caster sugar','granulated',
             'maple syrup','agave','molasses','golden syrup','chocolate','sucre','zucker']
SODIUM = ['soy sauce','fish sauce','oyster sauce','bouillon','stock cube','hoisin','teriyaki',
          'worcestershire','maggi','dashi']
MAYO = ['mayonnaise','mayonaise','mayo','ranch dressing']
SPIRITS = ['bourbon','whiskey','whisky','rum','vodka','tequila','brandy','cognac','liqueur',
           'triple sec','grand marnier','cointreau','kirsch','sherry','port wine','marsala']
NEUTRAL_OIL = ['vegetable oil','canola','canola oil','sunflower oil','corn oil','grapeseed',
               'peanut oil','rapeseed','shortening']

def classify(ingredients):
    """Return dict of category -> list of {label, points, note, matched} for a recipe."""
    good = {}   # label -> record
    bad = {}
    def add_good(store, label, group, points, note):
        if label not in store:
            store[label] = {'label': label, 'group': group, 'points': points, 'note': note}
    def add_bad(store, label, group, sev, points, note):
        if label not in store or store[label]['points'] < points:
            store[label] = {'label': label, 'group': group, 'severity': sev, 'points': points, 'note': note}

    for raw in ingredients:
        l = ' ' + raw.lower() + ' '
        af = amount_factor(l)

        # ---- OIL disambiguation (specific first) ----
        if has(l, 'olive oil') or has(l, 'extra virgin', 'extra-virgin'):
            add_good(good, 'olive oil', 'OLIVE_OIL', 10, 'Primary Mediterranean fat ⭐')
        elif has(l, *NEUTRAL_OIL):
            m = next((w for w in NEUTRAL_OIL if has(l, w)), 'neutral oil')
            add_bad(bad, m, 'NEUTRAL_OIL', 'MILD', 2*af, 'Use olive oil instead')

        # ---- BUTTER / CREAM / animal fat (guard butternut, buttermilk, nut butter) ----
        if (re.search(r'(?<![a-z])butter(?![a-z])', l) or re.search(r'(?<![a-z])beurre', l)) and not re.search(
                r'(?:pea|al|cocoa|apple|nut|body|shea)\s*butter|butter\s*(?:nut|milk)|butternut|buttermilk', l):
            add_bad(bad, 'butter', 'BUTTER_CREAM', 'HIGH', 7*af, 'Swap for olive oil')
        if (re.search(r'(?<![a-z])cream(?![a-z])', l) or re.search(r'(?<![a-z])(cr[eè]me|sahne)(?![a-z])', l)) \
                and not has(l, 'cream of tartar', 'ice cream') and not re.search(r'crème fraîche|creme fraiche', l):
            add_bad(bad, 'cream', 'BUTTER_CREAM', 'HIGH', 7*af, 'Heavy dairy fat — use yogurt or skip')
        if re.search(r'crème fraîche|creme fraiche', l):
            add_bad(bad, 'crème fraîche', 'BUTTER_CREAM', 'HIGH', 7*af, 'Heavy dairy fat — use yogurt or skip')
        if has(l, 'sour cream'):
            add_bad(bad, 'sour cream', 'BUTTER_CREAM', 'HIGH', 7*af, 'Swap Greek yogurt')
        if has(l, 'half and half', 'half-and-half'):
            add_bad(bad, 'half and half', 'BUTTER_CREAM', 'HIGH', 7*af, 'Heavy dairy — use milk or Greek yogurt')
        if has(l, 'lard', 'ghee', 'tallow', 'suet', 'duck fat', 'margarine', 'crisco', 'drippings'):
            m = next((w for w in ['lard','ghee','tallow','suet','duck fat','margarine','crisco','drippings'] if has(l, w)), 'animal fat')
            add_bad(bad, m, 'BUTTER_CREAM', 'HIGH', 7*af, 'Solid/animal fat — use olive oil')

        # ---- TROPICAL fats ----
        for w in TROPICAL:
            if has(l, w):
                add_bad(bad, w, 'TROPICAL', 'HIGH', 5*af, 'High saturated fat — limit'); break

        # ---- PROCESSED MEAT (check before red meat so pork sausage -> processed) ----
        procmatch = None
        for w in PROCESSED_MEAT:
            if w == 'ham':
                if re.search(r'(?<![a-z])ham(?![a-z])', l) and not re.search(r'hamburger|graham', l):
                    procmatch = 'ham'; break
            elif has(l, w):
                procmatch = w; break
        if procmatch:
            add_bad(bad, procmatch, 'PROCESSED_MEAT', 'SEVERE', 14*af, 'Processed/cured meat — strongly limit 🔴')

        # ---- RED MEAT (skip if this line already processed) ----
        if not procmatch:
            for w in RED_MEAT:
                if has(l, w):
                    # skip only when the word is the fat/stock form: "beef fat", "beef stock/broth"
                    if re.search(re.escape(w) + r's?\s+(fat|stock|broth|bouillon|drippings|consomm)', l):
                        break
                    add_bad(bad, w, 'RED_MEAT', 'HIGH', 9*af, 'Red meat — a few times a month 🟠'); break

        # ---- POULTRY (positive-ish; guard broth/stock/fat) ----
        if (has(l, 'chicken','turkey','duck') and not re.search(
                r'(chicken|turkey|duck)\s*(stock|broth|bouillon|fat)', l)):
            add_good(good, 'poultry', 'POULTRY', 3, 'Poultry — preferred over red meat')

        # ---- FISH ----
        # Strip condiment / non-protein forms so they don't count as a seafood protein:
        # "fish sauce", "oyster sauce" are seasonings (penalised elsewhere as sodium);
        # "oyster mushroom" is a vegetable.
        lf = re.sub(r'fish sauce|oyster sauce|oyster mushroom|clam juice', ' ', l)
        if has(lf, *OILY_FISH):
            m = next((w for w in OILY_FISH if has(lf, w)), 'oily fish')
            add_good(good, m, 'FISH', 12, 'Oily fish, omega-3 ⭐')
        elif has(lf, *FISH_SEAFOOD):
            m = next((w for w in FISH_SEAFOOD if has(lf, w)), 'seafood')
            add_good(good, m, 'FISH', 9, 'Fish/seafood — preferred protein ✓')

        # ---- LEGUMES (guard green bean / vanilla / coffee bean) ----
        for w in LEGUME:
            if has(l, w):
                add_good(good, w, 'LEGUME', 12, 'Legume — signature Mediterranean food ⭐'); break
        else:
            if re.search(r'(?<![a-z])beans?(?![a-z])', l) and not re.search(
                    r'green bean|vanilla bean|coffee bean|cocoa bean|soybean|bean sprout', l):
                add_good(good, 'beans', 'LEGUME', 12, 'Legume — signature Mediterranean food ⭐')

        # ---- WHOLE GRAINS ----
        for w in WHOLEGRAIN:
            if has(l, w):
                add_good(good, w, 'WHOLEGRAIN', 8, 'Whole grain ✓'); break

        # ---- RICE disambiguation ----
        if re.search(r'(?<![a-z])rice(?![a-z])', l) and not has(
                l, 'brown rice','wild rice','rice vinegar','rice wine','rice paper','rice noodle',
                'rice flour','wild-rice'):
            if has(l, 'white rice','jasmine','basmati','arborio','sushi rice','long grain','long-grain') or \
               (not has(l, 'noodle','vinegar','wine','paper','flour','cake','pudding','cooker mexican')):
                add_bad(bad, 'white rice', 'REFINED_GRAIN', 'MODERATE', 5*af, 'Refined grain — swap brown/wild rice')

        # ---- REFINED FLOUR / BREAD / PASTA ----
        if has(l, 'all-purpose','all purpose','white flour','plain flour','bread flour','cake flour',
               '00 flour','pastry flour','farine','mehl') or (re.search(r'(?<![a-z])flour(?![a-z])', l) and not has(
                l, 'whole wheat','whole-wheat','almond flour','coconut flour','rice flour','chickpea flour',
                'buckwheat','corn flour','cornflour','oat flour','semolina','masa')):
            add_bad(bad, 'refined flour', 'REFINED_GRAIN', 'MODERATE', 5*af, 'Refined grain — prefer whole grain')
        if (has(l, 'pasta','spaghetti','penne','fettuccine','linguine','macaroni','noodle','noodles',
                'lasagna','lasagne','tagliatelle','rigatoni','fusilli','orzo','ziti','tortellini') and not
            has(l, 'whole wheat','whole-wheat','whole grain','rice noodle','soba','glass noodle','shirataki')):
            add_bad(bad, 'refined pasta', 'REFINED_GRAIN', 'MODERATE', 5*af, 'Refined grain — try whole-wheat pasta')
        if (has(l, 'white bread','baguette','bread','breadcrumb','panko','pita','naan','tortilla',
                'brioche','croissant','bun','buns','roll','rolls','pizza dough','puff pastry','pastry') and not
            has(l, 'whole wheat','whole-wheat','whole grain','wholegrain')):
            add_bad(bad, 'refined bread/pastry', 'REFINED_GRAIN', 'MODERATE', 4*af, 'Refined grain — choose whole grain')

        # ---- WHITE POTATO (guard sweet potato) ----
        if (re.search(r'(?<![a-z])potato(e?s)?(?![a-z])', l) or
                has(l, 'pomme de terre','pommes de terre','kartoffel','kartoffeln','frite','frites',
                    'pommes frites')) and not has(l, 'sweet potato','sweet potatoes'):
            add_bad(bad, 'potato', 'WHITE_POTATO', 'MILD', 2*af, 'Starchy — moderate, prefer whole grains/veg')

        # ---- SUGAR ----
        for w in SUGAR_SEVERE:
            if has(l, w):
                add_bad(bad, w, 'ADDED_SUGAR', 'SEVERE', 8*af, 'Concentrated added sugar 🔴'); break
        else:
            for w in SUGAR_MOD:
                if has(l, w):
                    add_bad(bad, 'sugar', 'ADDED_SUGAR', 'MODERATE', 3*af, 'Added sugar — keep occasional'); break

        # ---- SODIUM ----
        for w in SODIUM:
            if has(l, w):
                add_bad(bad, w, 'SODIUM', 'MODERATE', 3*af, 'High-sodium — season with herbs instead'); break

        # ---- MAYO ----
        if has(l, *MAYO):
            add_bad(bad, 'mayonnaise', 'MAYO', 'MODERATE', 3*af, 'Creamy dressing — try olive-oil/yogurt')

        # ---- SPIRITS (wine is allowed, so excluded) ----
        for w in SPIRITS:
            if has(l, w):
                add_bad(bad, w, 'SPIRITS', 'MILD', 2*af, 'Spirits/liqueur — wine in moderation is the norm'); break

        # ---- VEGETABLES ----
        for w in VEG:
            if has(l, w):
                add_good(good, canon(w), 'VEG', 2.5, 'Vegetable ✓')  # keep counting others
        # ---- AROMATICS / HERBS ----
        for w in AROMATIC:
            if has(l, w):
                add_good(good, canon(w), 'AROMATIC', 1, 'Herb/spice/aromatic +')
        # ---- NUTS / SEEDS ----
        for w in NUTS:
            if has(l, w):
                add_good(good, canon(w), 'NUTS', 3, 'Nuts/seeds ✓')
        # ---- FRUIT ----
        for w in FRUIT:
            if has(l, w):
                add_good(good, canon(w), 'FRUIT', 2, 'Fruit ✓')
        # ---- DAIRY (good, moderate) ----
        for w in DAIRY_GOOD:
            if has(l, w):
                add_good(good, w, 'DAIRY_GOOD', 2, 'Yogurt/traditional cheese in moderation +')
        # ---- GOOD EXTRA ----
        for w in GOOD_EXTRA:
            if has(l, w):
                add_good(good, w.rstrip('s'), 'GOOD_EXTRA', 2, 'Mediterranean staple +')

    return good, bad

# caps per group
POS_CAP = {'OLIVE_OIL':10,'LEGUME':12,'FISH':12,'WHOLEGRAIN':8,'VEG':15,'NUTS':6,
           'FRUIT':6,'AROMATIC':4,'POULTRY':3,'DAIRY_GOOD':4,'GOOD_EXTRA':4}
NEG_CAP = {'PROCESSED_MEAT':24,'RED_MEAT':18,'BUTTER_CREAM':14,'TROPICAL':10,'REFINED_GRAIN':10,
           'ADDED_SUGAR':16,'SODIUM':6,'MAYO':6,'NEUTRAL_OIL':4,'WHITE_POTATO':4,'SPIRITS':4,
           'CHEESE_HEAVY':5,'FRIED':10}

SEV_RANK = {'SEVERE':4,'HIGH':3,'MODERATE':2,'MILD':1}
TIER_LABEL = {'OLIVE_OIL':'SIGNATURE','LEGUME':'SIGNATURE','FISH':'SIGNATURE','WHOLEGRAIN':'GOOD',
              'VEG':'GOOD','NUTS':'GOOD','FRUIT':'GOOD','AROMATIC':'MINOR','POULTRY':'MINOR',
              'DAIRY_GOOD':'MINOR','GOOD_EXTRA':'MINOR'}

DESSERT_KW = ['cake','cookie','cookies','ice cream','pastry','pie','tart','brownie','cupcake','pudding',
              'mousse','cheesecake','scone','muffin','pavlova','financier','madeleine','galette','crisp',
              'frangipane','streusel','pops','popsicle','doughnut','donut','brioche','frosting','custard',
              'panna cotta','parfait','speculoos','gateau','gâteau','dessert','sweets']
# NB: 'sweet' (bare) is intentionally excluded — it false-matched "sweet potato",
# "sweetcorn", "sweet pepper". Dessert intent is caught by the specific words above
# plus the 'dessert'/'baking' categories.

def score_recipe(r, force_no_fry=False, force_no_cheese_heavy=False):
    # force_no_fry / force_no_cheese_heavy let the recipe-improver model a
    # method change (pan-sear instead of deep-fry) or "use less cheese".
    # Fall back to directions when the source had no ingredients block (a few recipes)
    ing_source = r['ingredients'] if r['ingredients'] else (r.get('directions') or [])
    good, bad = classify(ing_source)
    # sum with caps
    pos_by_group = {}
    for rec in good.values():
        pos_by_group.setdefault(rec['group'], 0)
        pos_by_group[rec['group']] += rec['points']
    pos_total = 0
    for g, v in pos_by_group.items():
        pos_total += min(v, POS_CAP.get(g, v))

    # cheese-heavy detection
    name = (r['name'] or '').lower()
    cats = ' '.join(r.get('categories') or []).lower()
    text = ' '.join(r['ingredients']).lower()
    cheese_heavy = False
    if has(name, 'mac and cheese','macaroni','alfredo','queso','cheese dip','gratin','croquettes',
           'cheese bread','quiche') or has(cats, 'cheese'):
        cheese_heavy = True
    # large cheese quantity
    if re.search(r'(\d+)\s*(cup|cups|pound|lb).{0,20}(cheese|cheddar|gruy|mozzarella|parmesan)', text):
        cheese_heavy = True
    if force_no_cheese_heavy:
        cheese_heavy = False

    # ---- deep-fry method detection (from directions) ----
    directions = ' '.join(r.get('directions') or []).lower()
    deep_fried = bool(re.search(r'deep[\s-]?fr|for frying|deep fry|fry(er| in \d| in (vegetable|canola|peanut))|'
                                r'submerge.*oil|friture|frire|frituur', directions + ' ' + name)) \
                 or has(name, 'frites','fries','fried','tempura','karaage','katsu','croquettes','beignets')
    if force_no_fry:
        deep_fried = False
    if deep_fried:
        bad['deep-fried (cooking method)'] = {'label':'deep-fried (cooking method)','group':'FRIED',
            'severity':'SEVERE','points':10,'note':'Deep-frying — off-pattern cooking method 🔴'}

    neg_by_group = {}
    for rec in bad.values():
        neg_by_group.setdefault(rec['group'], 0)
        neg_by_group[rec['group']] += rec['points']
    if cheese_heavy:
        neg_by_group['CHEESE_HEAVY'] = 5
        bad['cheese (as main component)'] = {'label':'cheese (as main component)','group':'CHEESE_HEAVY',
                                             'severity':'MODERATE','points':5,'note':'Cheese-forward dish — heavy saturated fat'}
    neg_total = 0
    for g, v in neg_by_group.items():
        neg_total += min(v, NEG_CAP.get(g, v))

    # ---- modifiers ----
    modifiers = []
    is_dessert = has(name, *DESSERT_KW) or has(cats, 'dessert','sweet','baking')
    has_meat = any(g in neg_by_group for g in ('RED_MEAT','PROCESSED_MEAT')) or 'POULTRY' in pos_by_group or 'FISH' in pos_by_group
    fruit_nut_dessert = is_dessert and ('FRUIT' in pos_by_group or 'NUTS' in pos_by_group) and 'ADDED_SUGAR' not in neg_by_group
    if is_dessert and not fruit_nut_dessert:
        neg_total += 4; modifiers.append('-4 dessert/sweet (off-pattern treat)')
    meat_in_text = bool(re.search(r'(?<![a-z])(chicken|beef|pork|lamb|veal|turkey|duck|bacon|ham|sausage|'
                                  r'fish|salmon|shrimp|prawn|boeuf|porc|poulet|jambon|viande)', text))
    plant_only = (not has_meat) and (not meat_in_text) and \
                 ('VEG' in pos_by_group or 'LEGUME' in pos_by_group) and not is_dessert
    if plant_only:
        pos_total += 4; modifiers.append('+4 plant-based vegetarian dish')
    meat_penalty = any(g in neg_by_group for g in ('RED_MEAT','PROCESSED_MEAT'))
    if 'FISH' in pos_by_group and 'OLIVE_OIL' in pos_by_group and 'VEG' in pos_by_group and not meat_penalty:
        pos_total += 4; modifiers.append('+4 textbook Mediterranean plate (fish + olive oil + veg)')

    raw = 50 + pos_total - neg_total
    score = max(0, min(100, round(raw)))

    if score >= 85: grade = 'A'
    elif score >= 70: grade = 'B'
    elif score >= 55: grade = 'C'
    elif score >= 40: grade = 'D'
    else: grade = 'F'

    # ---- build ingredient lists ----
    good_list = sorted(good.values(), key=lambda x: -x['points'])
    bad_list = sorted(bad.values(), key=lambda x: (-SEV_RANK[x['severity']], -x['points']))
    good_out = [{'ingredient': g['label'], 'tier': TIER_LABEL.get(g['group'],'GOOD'), 'note': g['note']} for g in good_list]
    bad_out = [{'ingredient': b['label'], 'severity': b['severity'], 'note': b['note'],
                'penalty': round(b['points'],1)} for b in bad_list]

    # ---- suggestions ----
    sug = []
    groups_bad = set(neg_by_group)
    if 'BUTTER_CREAM' in groups_bad: sug.append('Cook with extra-virgin olive oil instead of butter/cream.')
    if 'REFINED_GRAIN' in groups_bad: sug.append('Swap refined grains for whole grains (brown rice, whole-wheat, bulgur).')
    if 'PROCESSED_MEAT' in groups_bad: sug.append('Drop or greatly reduce cured/processed meat; use it as a small accent at most.')
    if 'RED_MEAT' in groups_bad: sug.append('Treat red meat as a condiment — smaller portions, more vegetables/legumes.')
    if 'ADDED_SUGAR' in groups_bad: sug.append('Reduce added sugar; finish with fresh fruit.')
    if 'TROPICAL' in groups_bad: sug.append('Replace coconut/palm fat with olive oil where possible.')
    if 'SODIUM' in groups_bad: sug.append('Cut high-sodium sauces; lean on herbs, lemon, and spices.')
    if 'NEUTRAL_OIL' in groups_bad: sug.append('Switch the neutral cooking oil (canola/vegetable) to extra-virgin olive oil.')
    if 'MAYO' in groups_bad: sug.append('Replace mayonnaise with an olive-oil or yogurt-based dressing.')
    if 'LEGUME' not in pos_by_group and 'VEG' in pos_by_group and not is_dessert:
        sug.append('Add legumes (chickpeas, lentils, beans) to boost the Mediterranean profile.')

    # ---- comment ----
    comment = build_comment(grade, score, pos_by_group, neg_by_group, is_dessert, plant_only, cheese_heavy)

    return {
        'id': r.get('id'),
        'name': r['name'],
        'score': score,
        'grade': grade,
        'is_dessert': bool(is_dessert),
        'non_food': bool(r.get('non_food')),
        'out_of_scope': bool(r.get('out_of_scope')),
        'out_of_scope_reason': r.get('out_of_scope_reason'),
        'duplicate_of': r.get('duplicate_of'),
        'categories': r.get('categories') or [],
        'comment': comment,
        'good_ingredients': good_out,
        'bad_ingredients': bad_out,
        'suggestions': sug,
        'breakdown': {
            'base': 50,
            'positive_total': round(pos_total,1),
            'negative_total': round(neg_total,1),
            'positive_by_group': {k: round(min(v, POS_CAP.get(k,v)),1) for k,v in pos_by_group.items()},
            'negative_by_group': {k: round(min(v, NEG_CAP.get(k,v)),1) for k,v in neg_by_group.items()},
            'modifiers': modifiers,
        },
    }

def build_comment(grade, score, pos, neg, is_dessert, plant_only, cheese_heavy):
    good_bits = []
    if 'OLIVE_OIL' in pos: good_bits.append('olive oil')
    if 'LEGUME' in pos: good_bits.append('legumes')
    if 'FISH' in pos: good_bits.append('fish/seafood')
    if 'VEG' in pos: good_bits.append('plenty of vegetables')
    if 'WHOLEGRAIN' in pos: good_bits.append('whole grains')
    if 'NUTS' in pos: good_bits.append('nuts/seeds')
    bad_bits = []
    if 'PROCESSED_MEAT' in neg: bad_bits.append('cured/processed meat')
    if 'RED_MEAT' in neg: bad_bits.append('red meat')
    if 'BUTTER_CREAM' in neg: bad_bits.append('butter/cream')
    if 'REFINED_GRAIN' in neg: bad_bits.append('refined grains')
    if 'ADDED_SUGAR' in neg: bad_bits.append('added sugar')
    if cheese_heavy: bad_bits.append('heavy cheese')

    head = {
        'A': 'Core Mediterranean — eat freely.',
        'B': 'Solidly Mediterranean-friendly.',
        'C': 'Moderately Mediterranean — fine occasionally or with small tweaks.',
        'D': 'Off-pattern — best as an occasional treat.',
        'F': 'Not Mediterranean — save for rare indulgences.',
    }[grade]
    parts = [head]
    if good_bits: parts.append('Builds on ' + ', '.join(good_bits) + '.')
    if bad_bits: parts.append('Held back by ' + ', '.join(bad_bits) + '.')
    if is_dessert: parts.append('It is a sweet/dessert, inherently a "top of the pyramid" food.')
    elif plant_only: parts.append('Plant-forward and meat-free — a Mediterranean strength.')
    return ' '.join(parts)

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    data = json.load(open(SRC))
    scored = [score_recipe(r) for r in data['recipes']]
    scored.sort(key=lambda x: (-x['score'], x['name'].lower()))

    with open(os.path.join(OUT_DIR,'recipe_mediterranean_scores.json'),'w',encoding='utf-8') as fh:
        json.dump({'recipe_count': len(scored),
                   'scoring_reference': 'mediterranean_scoring_system.md',
                   'recipes': scored}, fh, ensure_ascii=False, indent=2)

    # ---------------------------------------------------------------------------
    # Markdown report
    # ---------------------------------------------------------------------------
    from collections import Counter
    gc = Counter(s['grade'] for s in scored)
    SEV_EMOJI = {'SEVERE':'🔴','HIGH':'🟠','MODERATE':'🟡','MILD':'⚪'}
    TIER_EMOJI = {'SIGNATURE':'⭐','GOOD':'✓','MINOR':'+'}
    GRADE_DESC = {'A':'Core Mediterranean — eat freely','B':'Mediterranean-friendly — regular rotation',
                  'C':'Moderate — occasional / easy tweaks','D':'Off-pattern — occasional treat',
                  'F':'Not Mediterranean — rare indulgence'}

    def md_report(scored):
        L = []
        L.append('# Mediterranean-Diet Recipe Scores\n')
        L.append('Every recipe scored 0–100 for fit with the Mediterranean eating pattern. '
                 'Methodology: `mediterranean_scoring_system.md`. Reference: `mediterranean_diet_wiki.md`.\n')
        L.append(f'**{len(scored)} recipes scored.** Average score: '
                 f'**{round(sum(s["score"] for s in scored)/len(scored),1)}/100**.\n')
        # grade distribution
        L.append('## Grade distribution\n')
        L.append('| Grade | Meaning | Count |')
        L.append('|---|---|---|')
        for g in 'ABCDF':
            L.append(f'| **{g}** | {GRADE_DESC[g]} | {gc.get(g,0)} |')
        L.append('')
        # legend
        L.append('## Legend\n')
        L.append('**Good ingredients:** ⭐ SIGNATURE (olive oil, legumes, fish) · ✓ GOOD (veg, whole grains, nuts, fruit) · + MINOR (herbs, poultry, yogurt).\n')
        L.append('**Bad ingredients (severity = how far off-pattern):** 🔴 SEVERE (processed meat, deep-frying, concentrated sugar) · 🟠 HIGH (red meat, butter/cream, tropical fat) · 🟡 MODERATE (refined grains, heavy cheese, added sugar, high sodium) · ⚪ MILD (neutral oils, white potato, spirits). The number in parentheses is the point penalty applied.\n')
        # leaderboard
        L.append('## Leaderboard\n')
        L.append('| # | Score | Grade | Recipe |')
        L.append('|---|---|---|---|')
        for i, s in enumerate(scored, 1):
            L.append(f'| {i} | {s["score"]} | {s["grade"]} | {s["name"]} |')
        L.append('')
        # per-grade detail
        L.append('---\n\n# Detailed scorecards\n')
        for g in 'ABCDF':
            group = [s for s in scored if s['grade']==g]
            L.append(f'## Grade {g} — {GRADE_DESC[g]} ({len(group)} recipes)\n')
            for s in group:
                L.append(f'### {s["name"]} — {s["score"]}/100 ({g})\n')
                if s['categories']:
                    L.append(f'*Categories: {", ".join(s["categories"])}*\n')
                L.append(f'{s["comment"]}\n')
                if s['good_ingredients']:
                    items = ', '.join(f'{TIER_EMOJI.get(gi["tier"],"")} {gi["ingredient"]}' for gi in s['good_ingredients'])
                    L.append(f'**Good:** {items}\n')
                if s['bad_ingredients']:
                    items = ', '.join(f'{SEV_EMOJI.get(bi["severity"],"")} {bi["ingredient"]} (−{bi["penalty"]})' for bi in s['bad_ingredients'])
                    L.append(f'**Watch:** {items}\n')
                if s['suggestions']:
                    L.append('**To make it more Mediterranean:**')
                    for sug in s['suggestions']:
                        L.append(f'- {sug}')
                    L.append('')
                bd = s['breakdown']
                L.append(f'<sub>Breakdown: base {bd["base"]} + positives {bd["positive_total"]} − negatives {bd["negative_total"]}'
                         + (f' · {"; ".join(bd["modifiers"])}' if bd['modifiers'] else '') + f' = **{s["score"]}**</sub>\n')
            L.append('')
        return '\n'.join(L)

    with open(os.path.join(OUT_DIR,'recipe_mediterranean_scores.md'),'w',encoding='utf-8') as fh:
        fh.write(md_report(scored))

    # stats
    print('Scored', len(scored), 'recipes')
    print('Grade distribution:', dict(sorted(gc.items())))
    print('Avg score:', round(sum(s['score'] for s in scored)/len(scored),1))
    print('\nTop 10:')
    for s in scored[:10]:
        print(f"  {s['score']:3d} {s['grade']}  {s['name']}")
    print('\nBottom 10:')
    for s in scored[-10:]:
        print(f"  {s['score']:3d} {s['grade']}  {s['name']}")
