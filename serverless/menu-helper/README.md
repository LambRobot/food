# Menu Helper — serverless backend

A tiny [Cloudflare Worker](https://workers.cloudflare.com/) that powers the **Menu Helper**
(`web/menu.html`). It holds your **Google Gemini** API key server-side and calls Gemini with vision +
the fatty-liver "least-worst option" rubric, returning a ranked verdict as JSON.

Why a Worker: GitHub Pages is static and can't hold a secret. The Worker is the small,
key-holding backend the browser calls. Cloudflare's free tier is plenty for personal use.

## One-time deploy

1. **Get a Gemini API key** — https://aistudio.google.com/app/apikey → Create API key. (Has a free
   tier; paid usage on a flash model is a fraction of a cent per menu.)

2. **Install Wrangler and log in** (Cloudflare's CLI):
   ```bash
   npm install -g wrangler        # or: brew install cloudflare-wrangler
   wrangler login                 # opens a browser to your (free) Cloudflare account
   ```

3. **Deploy the Worker** from this folder:
   ```bash
   cd serverless/menu-helper
   wrangler deploy
   ```
   Wrangler prints the Worker URL, e.g. `https://menu-helper.<your-subdomain>.workers.dev`.

4. **Store your API key as a secret** (never in the code):
   ```bash
   wrangler secret put GEMINI_API_KEY
   # paste your Gemini API key when prompted
   ```

5. **Point the web app at it:** open `web/menu.html`, find `const WORKER_URL = "..."` near the
   top of the script, and paste your Worker URL. Commit + push; GitHub Pages redeploys.

Done. Open the Menu Helper on your phone, snap a menu, get the ranking.

## Notes & knobs

- **Model / cost:** edit `MODEL` at the top of `worker.js`. Default `gemini-2.5-flash`;
  `gemini-2.5-flash-lite` is even cheaper.
- **Who can call it:** `ALLOWED_ORIGINS` in `worker.js` restricts browser calls to your Pages
  site + localhost. This is browser-level protection; for stronger protection against key abuse
  you can add a shared-secret header check, or set a spend cap in the
  Google AI Studio/Cloud console. For a personal tool, origin-restriction + a console spend cap is fine.
- **Redeploy after edits:** `wrangler deploy` again. Update the secret with
  `wrangler secret put GEMINI_API_KEY`.
- **Local test:** `wrangler dev` runs it at `http://localhost:8787`; temporarily point
  `WORKER_URL` there.

⚕︎ The Menu Helper gives educational, evidence-based suggestions — not medical advice.
