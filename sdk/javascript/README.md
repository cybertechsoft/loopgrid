# @cybertechsoft/loopgrid

TypeScript/JavaScript SDK for **LoopGrid — the evidence plane for AI agents**.

```bash
npm install @cybertechsoft/loopgrid
```

```js
const { LoopGrid } = require('@cybertechsoft/loopgrid');

const lg = new LoopGrid({
  baseUrl: 'http://localhost:8000',
  apiKey: process.env.LOOPGRID_SERVICE_KEY
});

const d = await lg.recordDecision({
  decision_type: 'customer_refund',
  agent: {id: 'support-agent', version: '1.0'},
  authority: {acting_for: 'Acme', limit_usd: 1500, scope: ['refund:create']},
  model: {provider: 'openai', name: 'gpt-5'},
  context: {prompt_version: 'support-v1'},
  proposed_action: {tool: 'stripe.refunds.create', amount: 720, currency: 'USD'}
});

console.log(d.decision_id);
console.log(await lg.verifyWorkspace());
```

v0.8 is a **design-partner release**, not Production GA.
