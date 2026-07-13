// Menu Helper — Cloudflare Worker (serverless proxy for the Claude API).
//
// Holds your ANTHROPIC_API_KEY (set as a secret, never in code) and calls Claude
// with vision + the fatty-liver "least-worst option" rubric. The web app POSTs a
// menu photo here and gets back a ranked JSON verdict. See README.md to deploy.
//
// Uses raw fetch (no dependencies) so it deploys as a single file with `wrangler deploy`.

// --- model: default is the most capable; switch to a cheaper one if cost matters ---
//   "claude-opus-4-8"   ~$5/$25 per 1M tokens  (default, best reasoning)
//   "claude-sonnet-4-6" ~$3/$15 per 1M tokens  (good, cheaper)
//   "claude-haiku-4-5"  ~$1/$5  per 1M tokens  (cheapest; fine for menus)
const MODEL = "claude-opus-4-8";

// Only these origins may call the Worker from a browser (protects your key from
// casual reuse). Add your Pages URL; localhost is for testing.
const ALLOWED_ORIGINS = [
  "https://lambrobot.github.io",
  "http://localhost:8765",
  "http://127.0.0.1:8765",
];

const SYSTEM = `You are a "least-worst option" dining advisor for a person managing fatty liver disease (MASLD).
You are shown a photo of a menu (or a description of a place). Rank the items that are the BEST AVAILABLE CHOICES for a fatty-liver diet — the goal is never a perfect meal, it is the best decision available in that moment.

Priorities, in order (biggest liver wins first):
1. Avoid sugary drinks (soda, juice, sweet tea, sweet coffee) — added sugar/fructose is the #1 driver of liver fat.
2. Avoid alcohol.
3. Prefer protein that is grilled / baked / roasted / steamed — never fried, breaded, or "crispy".
4. Favor vegetables, salads (dressing on the side), fish/seafood, beans/lentils, whole grains, olive oil.
5. Cut refined-carb bases (big buns, white-rice mounds, pasta, garlic bread) — halve or skip.
6. Prefer smaller portions.
Red flags: fried/"crispy"/tempura, sweet-glazed sauces (BBQ, teriyaki, sweet-and-sour, honey-glazed, general tso's), creamy/cheesy ("alfredo", "queso", "smothered", "loaded"), bacon/sausage/processed meat, desserts/pastries.

Read the actual menu in the image. Pick 1–3 REAL items from it that are the least-worst, best first. For each, give a fatty-liver letter grade (A best … F worst — most restaurant items land C–F, that's expected), one short reason it's better and what drags it down, and one line of easy tweaks (e.g. "get it grilled, dressing on the side, water instead of soda"). Also list the 2–4 worst items to avoid. In the note, be honest about confidence: if the menu gives only names with no detail, say the ranking is directional. This is educational, not medical advice.`;

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    place: { type: "string", description: "Restaurant/place name if visible, else a short description of the menu" },
    picks: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          name: { type: "string" },
          grade: { type: "string", enum: ["A", "B", "C", "D", "F"] },
          why: { type: "string" },
          tweaks: { type: "string" },
        },
        required: ["name", "grade", "why", "tweaks"],
      },
    },
    avoid: { type: "array", items: { type: "string" } },
    note: { type: "string" },
  },
  required: ["place", "picks", "avoid", "note"],
};

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Vary": "Origin",
  };
}

function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, "content-type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request.headers.get("Origin") || "");
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "POST") return json({ error: "POST a menu image." }, 405, cors);
    if (!env.ANTHROPIC_API_KEY) return json({ error: "Server missing ANTHROPIC_API_KEY." }, 500, cors);

    let body;
    try { body = await request.json(); } catch { return json({ error: "Invalid JSON." }, 400, cors); }
    const { image, media_type, note } = body;
    if (!image) return json({ error: "No image provided." }, 400, cors);

    const userText = (note ? `Extra context from the diner: ${note}\n\n` : "") +
      "Rank the least-worst fatty-liver-friendly options on this menu.";

    let apiResp;
    try {
      apiResp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: MODEL,
          max_tokens: 2000,
          system: SYSTEM,
          output_config: { format: { type: "json_schema", schema: SCHEMA } },
          messages: [{
            role: "user",
            content: [
              { type: "image", source: { type: "base64", media_type: media_type || "image/jpeg", data: image } },
              { type: "text", text: userText },
            ],
          }],
        }),
      });
    } catch (e) {
      return json({ error: "Could not reach the model API." }, 502, cors);
    }

    const data = await apiResp.json();
    if (!apiResp.ok) return json({ error: data?.error?.message || "Model API error." }, 502, cors);
    if (data.stop_reason === "refusal")
      return json({ error: "The model declined to analyze that image. Try a clearer menu photo." }, 200, cors);

    // structured output guarantees the first text block is valid JSON matching SCHEMA
    const text = (data.content || []).find((b) => b.type === "text")?.text;
    if (!text) return json({ error: "Empty response from the model." }, 502, cors);
    return new Response(text, { status: 200, headers: { ...cors, "content-type": "application/json" } });
  },
};
