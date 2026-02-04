# Contributing to LoopGrid

LoopGrid is a control plane for AI decision reliability.

We welcome contributions, but LoopGrid is **opinionated infrastructure**. Please read this guide before submitting changes.

---

## What We Accept

### ✅ SDK Improvements
- Bug fixes
- Type hints and docstrings
- Performance improvements
- New language SDKs (Go, Rust, etc.)

### ✅ Documentation
- Guides and tutorials
- API documentation
- Architecture clarifications
- Example integrations

### ✅ Schema Corrections
- JSON schema fixes
- OpenAPI spec improvements
- Validation improvements

### ✅ Backend Improvements
- Bug fixes
- Performance improvements
- Database compatibility (PostgreSQL, etc.)
- Security improvements

---

## What We Don't Accept

### ❌ Dashboards / Visualization
There is intentionally no UI. LoopGrid is infrastructure.

### ❌ Auto-Fix / Automation Features
Replay comes before automation. We don't auto-fix decisions.

### ❌ Analytics / Metrics
Analytics are downstream of the ledger. Not core scope.

### ❌ Scope Expansion
Feature creep dilutes the system of record.

---

## How to Submit

1. **Fork** the repository
2. **Create a branch** named `fix/<issue>` or `feature/<description>`
3. **Follow code style** (PEP8 for Python, ESLint for JS)
4. **Write tests** if applicable
5. **Submit a pull request** with clear description

---

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/loopgrid.git
cd loopgrid

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Start the server
python run_server.py

# Run the demo
python test_demo.py
```

---

## Code Style

### Python
- Follow PEP8
- Use type hints
- Write docstrings for public functions

### JavaScript
- Use ESLint
- Use JSDoc comments
- Support both CommonJS and ES modules

---

## Pull Request Guidelines

1. **One feature per PR** — keep changes focused
2. **Write tests** — if you add functionality
3. **Update docs** — if you change APIs
4. **Reference issues** — link to related issues

---

## Code of Conduct

- Be respectful and professional
- Decisions are immutable; discussions should be disciplined
- Disagreements resolved by design principle alignment

---

## Questions?

Open an issue or reach out to the maintainers.

---

**LoopGrid is intentionally minimal.** 

We prioritize clarity, correctness, and minimalism over breadth.
