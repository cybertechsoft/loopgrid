# LoopGrid v0.5.1 — UI bootstrap hotfix

- Fixed a front-end initialization failure that could leave all UI buttons inert even while the FastAPI backend was healthy.
- Added DOM-ready bootstrap and defensive element binding.
- Added visible UI startup error reporting.
- Added static asset cache-busting and no-store behavior for local/design-partner builds.
- Replaced `String.replaceAll` with a wider-compatibility regex implementation.
- Added front-end smoke-test coverage for initial dashboard fetch and Load demo data click.
- Core v0.5 evidence, policy, review, API-key, OTLP/MCP, privacy, replay and verifier behavior is unchanged.
