# site/ — the interactive decision tool

A static, single-page site so a viewer can **feel** the tool: drag the
committee inputs and watch the enter / partner / decline trigger, the
live derivation, the funnel, the volume table and the cost × rate
decision surface all recompute. No build step, no dependencies, no
server — open `index.html` or deploy the folder.

## What's here

- `index.html` — the page (inputs, verdict, "how it came" derivation,
  decision surface, volume table, funnel, build log, hostile attacks,
  skills, tagged sources).
- `model.js` — the same closed forms as the Python `model/` package
  (flip volume `F/(p−cv)`, the 5-yr PV break-even, CAC payback, the
  funnel, the (cost, rate) surface). UMD, so it loads in the browser
  **and** under Node.
- `app.js` — wires the sliders to `model.js`; one `render()` pass
  recomputes everything from the current inputs.
- `style.css` — the dark console styling.
- `verify.js` — the cross-language pin: asserts the JS numbers equal the
  Python baseline (`out/decision_numbers.json`) to the bit.

## Run it

```bash
node site/verify.js            # the JS pins match the Python baseline
node -e "require('http').createServer((q,s)=>{const fs=require('fs');s.end(fs.readFileSync('site/index.html'))}).listen(8080)"
# or just open site/index.html in a browser
```

## Deploy to Vercel

From the `site/` folder (so the page is served at the domain root, not
`/site/`):

```bash
cd site
npx vercel            # preview deploy
npx vercel --prod     # production deploy (returns the .vercel.app URL)
```

Redeploy after any edit the same way. To make it push-triggered, link the
project to this repo in the Vercel dashboard and set the **Root Directory**
to `site`.
