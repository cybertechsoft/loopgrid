# LoopGrid

**The control plane for AI decision reliability.**

A system of record for AI decisions. Capture every decision with cryptographic immutability, replay failures with live LLM re-execution, build ground truth from human corrections, and generate EU AI Act compliance reports.

---

## The Problem

AI systems make critical decisions in production. When they fail, teams can't answer basic questions:

- Why did the AI produce this output?
- Which prompt or model version was used?
- How would the decision change with different parameters?
- How do we systematically learn from human corrections?
- Can we prove compliance to regulators?

There is no system of record for AI decisions. Every failure is treated as a one-off.

## The Solution

LoopGrid provides the missing infrastructure layer:

| Component | What It Does |
|-----------|--------------|
| **Decision Ledger** | Immutable, hash-chained record of every AI decision |
| **Replay Engine** | Fork past decisions with live LLM re-execution or simulation |
| **Human Correction Loop** | Capture corrections as ground truth for learning |
| **Compliance Reports** | EU AI Act Article 12/14/9 compliance mapping |
| **Integrity Verification** | Cryptographic proof that the ledger hasn't been tampered with |

## Quick Start

### Installation

```bash
pip install loopgrid
```

### Basic Usage

```python
from loopgrid import LoopGrid

# Initialize
grid = LoopGrid(service_name="support-agent")

# Record an AI decision (cryptographically hashed and chained)
decision = grid.record_decision(
    decision_type="customer_support_reply",
    input={"message": "I was charged twice"},
    model={"provider": "openai", "name": "gpt-4"},
    prompt={"template": "support_v1"},
    output={"response": "Your account looks fine."}
)

# Mark as incorrect
grid.mark_incorrect(decision["decision_id"], reason="Missed billing issue")

# Replay with different prompt (live LLM call if API key set, otherwise simulated)
replay = grid.create_replay(
    decision_id=decision["decision_id"],
    overrides={"prompt": {"template": "support_v2"}}
)

# Attach human correction as ground truth
grid.attach_correction(
    decision_id=decision["decision_id"],
    correction={"response": "I see the duplicate charge. Refund initiated."},
    corrected_by="agent_42"
)

# Verify ledger integrity
integrity = grid.verify_integrity()
print(integrity)  # {"valid": True, "total": 1, ...}

# Generate compliance report
report = grid.compliance_report()
print(report["eu_ai_act_mapping"]["article_12_record_keeping"]["status"])
```

### Run Locally

```bash
# Clone the repo
git clone https://github.com/cybertechsoft/loopgrid.git
cd loopgrid

# Install dependencies
pip install -r requirements.txt

# Start the server
python run_server.py

# Run the demo (in another terminal)
python test_demo.py

# Run tests
python -m pytest tests/ -v
```

### Docker

```bash
docker-compose up
```

### Live Replay (Optional)

Set API keys to enable live LLM replay execution:

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
python run_server.py
```

Without API keys, replays use intelligent simulation mode.

## Core Concepts

### Decisions

A **decision** is any AI output that matters. Each decision captures full context and is **cryptographically hashed** — content hash (SHA-256 of decision data) plus chain hash (linking to previous decision). This creates a tamper-evident ledger.

### Replays

A **replay** is a forked execution of a past decision. Replays support **live LLM re-execution** (calls OpenAI/Anthropic APIs with overrides) or **simulation mode** (pattern-based, no API key needed).

### Corrections

**Human corrections** are ground truth. When a human fixes an AI output, that correction is linked to the original decision and becomes part of the immutable record.

### Compliance

LoopGrid maps decision data to **EU AI Act** requirements:
- **Article 12** — Record-keeping (automatic logging with hash chain integrity)
- **Article 14** — Human oversight (correction loop, flagging mechanism)
- **Article 9** — Risk management (error rate tracking, replay capability)

## API Reference

### REST API

```
POST   /v1/decisions                          Record a decision
GET    /v1/decisions/{id}                     Get decision
GET    /v1/decisions                          List decisions
POST   /v1/decisions/{id}/incorrect           Mark incorrect
POST   /v1/decisions/{id}/correction          Attach correction
GET    /v1/decisions/{id}/compare/{replay_id} Compare

POST   /v1/replays                            Create replay
GET    /v1/replays/{id}                       Get replay

GET    /v1/integrity/verify                   Verify hash chain
GET    /v1/compliance/report                  JSON compliance report
GET    /v1/compliance/report/html             Printable HTML report
GET    /v1/export/decisions                   Export decisions (JSON/CSV)
```

Full OpenAPI docs at `http://localhost:8000/docs` when running locally.

### Python SDK

```python
from loopgrid import LoopGrid
grid = LoopGrid(service_name="my-agent")

grid.record_decision(...)       # Record to ledger
grid.get_decision(id)           # Retrieve by ID
grid.list_decisions(...)        # List with filters
grid.mark_incorrect(id)         # Flag for review
grid.attach_correction(...)     # Ground truth
grid.create_replay(...)         # Fork execution
grid.compare(dec_id, rep_id)    # Side-by-side
grid.verify_integrity()         # Hash chain check
grid.compliance_report()        # EU AI Act report
```

### JavaScript SDK

```bash
npm install @cybertechsoft/loopgrid
```

```javascript
const { LoopGrid } = require('@cybertechsoft/loopgrid');
const grid = new LoopGrid({ serviceName: 'my-agent' });

await grid.recordDecision({ ... });
await grid.verifyIntegrity();
await grid.complianceReport();
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Your AI Application                    │
│         (Support Bot, Sales Agent, etc.)            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 LoopGrid SDK                        │
│            grid.record_decision()                   │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│             LoopGrid Control Plane                  │
│                                                     │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐  │
│  │ Decision  │ │  Replay  │ │  Human   │ │Compli-│  │
│  │  Ledger   │ │  Engine  │ │Correction│ │ ance  │  │
│  │(hash chain│ │(live LLM)│ │  Loop    │ │Reports│  │
│  └───────────┘ └──────────┘ └──────────┘ └───────┘  │
└─────────────────────────────────────────────────────┘
```

## Design Principles

1. **Decisions are immutable** — Cryptographically hashed and chained
2. **Replay precedes automation** — Understand before you automate
3. **Human correction is ground truth** — Corrections feed learning
4. **APIs over UI** — Infrastructure-first, SDK-first
5. **Narrow before broad** — Do one thing well

## Project Structure

```
loopgrid/
├── backend/app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models (hash chain)
│   ├── hashing.py           # SHA-256 hash chain
│   ├── llm_executor.py      # Live LLM replay execution
│   ├── config.py            # Environment configuration
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Database setup
│   └── routers/
│       ├── decisions.py     # Decision CRUD + hashing
│       ├── replays.py       # Replay engine
│       ├── integrity.py     # Chain verification
│       └── compliance.py    # EU AI Act reports
├── sdk/
│   ├── python/loopgrid/     # Python SDK
│   └── javascript/src/      # JavaScript SDK
├── tests/                   # Test suite
├── api/schemas/             # JSON schemas
├── examples/                # Usage examples
├── docs/                    # Documentation
└── website/                 # Landing page
```

## Roadmap

- [x] Python SDK
- [x] JavaScript SDK
- [x] Decision ledger with hash chain
- [x] Replay engine (live + simulated)
- [x] Human correction loop
- [x] Integrity verification
- [x] EU AI Act compliance reports
- [x] REST API with OpenAPI docs
- [x] Test suite
- [ ] PostgreSQL backend
- [ ] Docker deployment
- [ ] API authentication
- [ ] OpenAI/Anthropic SDK wrappers

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

**What we accept:** SDK improvements, schema fixes, docs, examples, tests

**What we don't accept:** Dashboards, auto-fix features, scope expansion

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

**LoopGrid** — Control Plane for AI Decision Reliability

[GitHub](https://github.com/cybertechsoft/loopgrid) · [PyPI](https://pypi.org/project/loopgrid/) · [npm](https://www.npmjs.com/package/@cybertechsoft/loopgrid)
