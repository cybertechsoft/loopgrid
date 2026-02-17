# LoopGrid Architecture

## Core Components

### 1. Decision Ledger
Immutable, SHA-256 hash-chained record of every AI decision. Each decision has content_hash + chain_hash. Tampering breaks the chain.

### 2. Replay Engine
Live LLM re-execution (OpenAI/Anthropic) or simulation fallback. Fork decisions with prompt/model/input overrides.

### 3. Human Correction Loop
Corrections linked to original decisions as immutable ground truth.

### 4. Compliance Reports
EU AI Act Articles 12, 14, 9 mapping. JSON + printable HTML output.

### 5. Integrity Verification
Hash chain walker that detects tampering, insertion, or deletion.
