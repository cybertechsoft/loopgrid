# LoopGrid

**The control plane for AI decision reliability.**

A system of record for AI decisions. Capture every decision immutably, replay failures with controlled overrides, and build ground truth from human corrections.

---

## The Problem

AI systems make critical decisions in production. When they fail, teams can't answer basic questions:

- Why did the AI produce this output?
- Which prompt or model version was used?
- How would the decision change with different parameters?
- How do we systematically learn from human corrections?

There is no system of record for AI decisions. Every failure is treated as a one-off.

## The Solution

LoopGrid provides the missing infrastructure layer:

| Component | What It Does |
|-----------|--------------|
| **Decision Ledger** | Immutable record of every AI decision with full context |
| **Replay Engine** | Fork past decisions with controlled overrides |
| **Human Correction Loop** | Capture corrections as ground truth for learning |

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

# Record an AI decision
decision = grid.record_decision(
    decision_type="customer_support_reply",
    input={"message": "I was charged twice"},
    model={"provider": "openai", "name": "gpt-4"},
    prompt={"template": "support_v1"},
    output={"response": "Your account looks fine."}
)

# Mark as incorrect
grid.mark_incorrect(decision["decision_id"], reason="Missed billing issue")

# Replay with different prompt
replay = grid.create_replay(
    decision_id=decision["decision_id"],
    overrides={"prompt": {"template": "support_v2"}}
)

# Attach human correction
grid.attach_correction(
    decision_id=decision["decision_id"],
    correction={"response": "I see the duplicate charge. Refund initiated."},
    corrected_by="agent_42"
)
```

### Run Locally

```bash
# Clone the repo
git clone https://github.com/cybertech/loopgrid.git
cd loopgrid

# Install dependencies
pip install -r requirements.txt

# Start the server
python run_server.py

# Run the demo (in another terminal)
python test_demo.py
```

## Core Concepts

### Decisions

A **decision** is any AI output that matters. Each decision captures:

- `input` — What triggered the decision
- `prompt` — Template and variables used
- `model` — Provider, name, version
- `output` — The AI's response
- `metadata` — Latency, tokens, custom fields

Decisions are **immutable**. Once recorded, they cannot be changed.

### Replays

A **replay** is a forked execution of a past decision. Use replays to:

- Test different prompts on the same input
- Compare model versions
- Debug failures systematically

### Corrections

**Human corrections** are ground truth. When a human fixes an AI output, that correction is linked to the original decision, enabling systematic learning.

## API Reference

### Python SDK

| Method | Description |
|--------|-------------|
| `record_decision()` | Record an AI decision to the ledger |
| `get_decision()` | Retrieve a decision by ID |
| `list_decisions()` | List decisions with filters |
| `mark_incorrect()` | Flag a decision as incorrect |
| `attach_correction()` | Attach human correction |
| `create_replay()` | Create a replay with overrides |
| `get_replay()` | Retrieve a replay by ID |
| `compare()` | Compare decision vs replay |

### REST API

```
POST   /v1/decisions              Record a decision
GET    /v1/decisions/{id}         Get decision
GET    /v1/decisions              List decisions
POST   /v1/decisions/{id}/incorrect    Mark incorrect
POST   /v1/decisions/{id}/correction   Attach correction

POST   /v1/replays                Create replay
GET    /v1/replays/{id}           Get replay
GET    /v1/decisions/{id}/compare/{replay_id}  Compare
```

Full OpenAPI docs at `http://localhost:8000/docs` when running locally.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Your AI Application                     │
│         (Support Bot, Sales Agent, etc.)            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 LoopGrid SDK                         │
│            grid.record_decision()                    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│             LoopGrid Control Plane                   │
│                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────────┐  │
│  │  Decision   │ │   Replay    │ │    Human      │  │
│  │   Ledger    │ │   Engine    │ │  Correction   │  │
│  └─────────────┘ └─────────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Design Principles

1. **Decisions are immutable** — Once recorded, never changed
2. **Replay precedes automation** — Understand before you automate
3. **Human correction is ground truth** — Corrections feed learning
4. **APIs over UI** — Infrastructure-first, SDK-first
5. **Narrow before broad** — Do one thing well

## Project Structure

```
loopgrid/
├── sdk/
│   ├── python/loopgrid/       # Python SDK
│   └── javascript/src/         # JavaScript SDK
├── backend/app/                # FastAPI backend
├── api/schemas/                # JSON schemas
├── examples/                   # Usage examples
├── docs/                       # Documentation
└── website/                    # Landing page
```

## Roadmap

- [x] Python SDK
- [x] Decision ledger
- [x] Replay engine
- [x] Human correction loop
- [x] REST API
- [ ] PostgreSQL backend
- [ ] JavaScript SDK (npm)
- [ ] Docker deployment
- [ ] API authentication

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

**What we accept:** SDK improvements, schema fixes, docs, examples

**What we don't accept:** Dashboards, auto-fix features, scope expansion

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

**LoopGrid** — Control Plane for AI Decision Reliability
