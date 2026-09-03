# LoopGrid v0.5.2

## UI runtime reliability hotfix

- Embedded the pilot UI runtime directly into `index.html`; the browser no longer depends on executing `/static/app.js`.
- Kept `app/static/app.js` as the maintainable source/runtime copy.
- Added `window.__loopgridRuntimeLoaded` and `window.__loopgridBooted` diagnostics.
- Added an idempotent 250 ms fallback boot attempt.
- Added a visible `<noscript>` diagnostic.
- Added `Cache-Control: no-store` to the root HTML in local/design-partner environments.
- Preserved all v0.5.1 APIs and evidence behavior.
