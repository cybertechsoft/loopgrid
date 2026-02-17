# Contributing to LoopGrid

LoopGrid is a control plane for AI decision reliability.

We welcome contributions, but LoopGrid is **opinionated infrastructure**. Please read this guide before submitting changes.

---

## What We Accept

- **SDK Improvements** — Bug fixes, type hints, performance, new language SDKs
- **Documentation** — Guides, tutorials, API docs, architecture clarifications
- **Schema Corrections** — JSON schema fixes, OpenAPI improvements, validation
- **Backend Improvements** — Bug fixes, performance, database compatibility, security
- **Tests** — New test coverage, edge case handling

## What We Don't Accept

- **Dashboards / Visualization** — There is intentionally no UI. LoopGrid is infrastructure.
- **Auto-Fix / Automation** — Replay comes before automation.
- **Analytics / Metrics** — Analytics are downstream. Not core scope.
- **Scope Expansion** — Feature creep dilutes the system of record.

## How to Submit

1. Fork the repository
2. Create a branch: `fix/<issue>` or `feature/<description>`
3. Follow code style (PEP8 for Python, ESLint for JS)
4. Write tests if applicable
5. Submit a pull request with clear description

## Development Setup

```bash
git clone https://github.com/cybertechsoft/loopgrid.git
cd loopgrid
pip install -r requirements.txt
python run_server.py     # Start server
python test_demo.py      # Run demo
python -m pytest tests/  # Run tests
```

## Code of Conduct

Be respectful and professional. Disagreements resolved by design principle alignment.

---

**LoopGrid is intentionally minimal.** We prioritize clarity, correctness, and minimalism over breadth.
