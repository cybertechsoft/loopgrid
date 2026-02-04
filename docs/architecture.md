# LoopGrid Architecture

## Overview

LoopGrid is the control plane for AI decision reliability. It provides infrastructure for capturing, replaying, and learning from AI decisions in production.

## Core Components

### 1. Decision Ledger

The **Decision Ledger** is an immutable record of every AI decision.

Each decision captures:
- `decision_id` — Unique identifier
- `timestamp` — When the decision was made
- `service_name` — Which service made it
- `decision_type` — Category of decision
- `input` — What triggered the decision
- `prompt` — Template and variables used
- `model` — Provider, name, version
- `output` — The AI's response
- `metadata` — Latency, tokens, custom fields

**Key Property:** Decisions are immutable. Once recorded, they cannot be modified.

### 2. Replay Engine

The **Replay Engine** enables forked executions of past decisions.

Features:
- Re-run any decision with the original context
- Apply overrides for prompt, model, or input
- Compare outputs side-by-side
- Track which replays led to improvements

**Use Cases:**
- Debugging failures
- A/B testing prompts
- Model version comparisons
- Systematic improvement

### 3. Human Correction Loop

The **Human Correction Loop** captures ground truth.

When a human corrects an AI output:
- The correction is linked to the original decision
- It becomes immutable ground truth
- It enables systematic learning
- It can feed into training data pipelines

## Data Flow

```
┌─────────────────────────────────────────┐
│           Your AI Application            │
│                                          │
│   1. Make AI call                        │
│   2. Get response                        │
│   3. Call grid.record_decision()         │
└─────────────────────┬────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│              LoopGrid SDK                │
│                                          │
│   - Validates decision schema            │
│   - Sends to control plane               │
└─────────────────────┬────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│         LoopGrid Control Plane           │
│                                          │
│   ┌──────────────────────────────────┐   │
│   │        Decision Ledger            │   │
│   │   (Immutable Storage)             │   │
│   └──────────────────────────────────┘   │
│                    │                      │
│   ┌────────────────┼────────────────┐    │
│   │                │                │    │
│   ▼                ▼                ▼    │
│ Replay        Correction         Query   │
│ Engine          Loop             API     │
└─────────────────────────────────────────┘
```

## Technology Stack

### V1 (Current)

| Layer | Technology |
|-------|------------|
| API | FastAPI |
| Database | SQLite |
| SDK | Python, JavaScript |
| Deployment | Local / Single server |

### V2 (Planned)

| Layer | Technology |
|-------|------------|
| API | FastAPI |
| Database | PostgreSQL |
| Queue | Redis |
| SDK | Python, JavaScript, Go |
| Deployment | Docker, Kubernetes |

## Decision Schema

```json
{
  "decision_id": "dec_abc123",
  "created_at": "2024-01-15T10:30:00Z",
  "service_name": "support-agent",
  "decision_type": "customer_support_reply",
  
  "input": {
    "message": "I was charged twice",
    "customer_id": "cust_123"
  },
  
  "model": {
    "provider": "openai",
    "name": "gpt-4",
    "version": "2024-01"
  },
  
  "prompt": {
    "template": "support_v1",
    "variables": {"tone": "friendly"}
  },
  
  "output": {
    "response": "Your account looks fine."
  },
  
  "status": "recorded",
  "metadata": {
    "latency_ms": 1240,
    "tokens": 150
  }
}
```

## Replay Schema

```json
{
  "replay_id": "rep_xyz789",
  "decision_id": "dec_abc123",
  "created_at": "2024-01-15T11:00:00Z",
  "triggered_by": "human_review",
  
  "overrides": {
    "prompt": {"template": "support_v2"}
  },
  
  "replay_output": {
    "response": "I see the duplicate charge. Refund initiated."
  },
  
  "output_changed": true,
  "diff_summary": "Output changed after replay with overrides"
}
```

## Security Considerations

### V1 Limitations
- No authentication (local use only)
- SQLite (not for high-scale)
- No encryption at rest

### Production Recommendations
- Run behind reverse proxy with TLS
- Add authentication at proxy level
- Use PostgreSQL for data integrity
- Enable audit logging
