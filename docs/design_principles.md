# LoopGrid Design Principles

These principles guide all LoopGrid development decisions.

---

## 1. Decisions Are Immutable

Once recorded, a decision cannot be modified.

**Why:** Immutability provides:
- Audit trail integrity
- Reproducibility guarantees
- Trust in the system of record

**Implication:** Corrections are stored separately and linked, never overwritten.

---

## 2. Replay Precedes Automation

Before automating anything, enable replay.

**Why:** You can't automate what you can't reproduce.

**Implication:** We build replay first, auto-fix later (if ever). Understanding comes before optimization.

---

## 3. Human Correction Is Ground Truth

When humans correct AI outputs, those corrections are the source of truth.

**Why:** Human judgment is the gold standard for AI improvement.

**Implication:** Corrections are first-class objects in the ledger, not afterthoughts.

---

## 4. APIs Over UI

LoopGrid is infrastructure, not a dashboard product.

**Why:** 
- Infrastructure integrates; dashboards isolate
- APIs scale; UIs don't
- Engineers trust code, not clicks

**Implication:** We ship SDKs and APIs first. UI is downstream (if ever).

---

## 5. Narrow Before Broad

Do one thing extremely well before expanding scope.

**Why:** Feature creep dilutes focus and quality.

**Implication:** 
- We say no to most feature requests
- We maintain a minimal, opinionated core
- Expansion is deliberate and justified

---

## 6. Everything Is Versioned

Prompts, models, tools, schemas — all versioned.

**Why:** Reproducibility requires knowing exactly what was used.

**Implication:** The decision schema captures version info for all components.

---

## 7. Infrastructure-First Language

We use infrastructure terms, not product marketing.

**Why:** Language shapes perception. We are infrastructure.

| ❌ Avoid | ✅ Use |
|----------|--------|
| Platform | Control plane |
| Dashboard | API |
| Users | Services / Teams |
| Monitor | Record / Replay |
| AI-powered | AI systems |

---

## 8. Contributions Are Curated

We accept improvements, not feature expansion.

**Why:** Opinionated software stays useful.

**Implication:**
- SDK improvements: Yes
- Schema fixes: Yes
- Dashboards: No
- Auto-fix: No
- Analytics: No

---

## Applying These Principles

When making decisions about LoopGrid:

1. Does it maintain immutability? 
2. Does it enable replay?
3. Does it respect human corrections?
4. Is it API-first?
5. Is it within narrow scope?
6. Does it use infra language?

If any answer is "no", reconsider.

---

*These principles are themselves versioned. Changes require clear justification.*
