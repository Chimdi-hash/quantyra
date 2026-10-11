# Quantyra — Intelligent Contract Submission Notes

## Category

Standalone GenLayer Intelligent Contract / reusable primitive.

**No frontend. No backend. No mock product state.** The Intelligent Contract is the source of truth.

## One-line purpose

Quantyra is a Decentralized Quantitative Strategy Risk Gateway that grounds capital-allocation risk decisions in contract-acquired market and counterparty evidence, strictly preserving consequential approval outcomes under GenLayer Optimistic Democracy.

## Why this needs GenLayer

1. **Contract-Acquired Web Evidence**: Capital-allocation risk cannot be evaluated responsibly in a vacuum. Quantyra actively fetches live market telemetry (volatility, liquidity) and counterparty health evidence from external HTTPS feeds (`gl.nondet.web.render`) inside consensus. Conventional smart contracts cannot do this without centralized oracles.
2. **Subjective Risk Synthesis Grounded in Evidence**: Translating unstructured market evidence and natural language strategy logic into quantitative risk vectors requires AI reasoning (`gl.nondet.exec_prompt`).
3. **Equivalence Principle with Consequential Invariant**: GenLayer's Optimistic Democracy enables validators to reach consensus on multi-vector risk scores while enforcing that validator tolerance **cannot cross the consequential approval threshold**.

## Consensus Design & Key Invariants

### 1. Evidence Acquisition Consensus
Leader and validators independently fetch the strategy's specified `evidence_url` via `gl.nondet.web.render(url, mode="text")`. If evidence acquisition fails or returns empty data on either side, the evaluation fails closed, automatically rejecting capital allocation.

### 2. Multi-Vector Risk Grounding
Acquired evidence is supplied directly into the LLM prompt. The assessment outputs:
- `market_risk` (1-10): Grounded in acquired market volatility/liquidity data.
- `counterparty_risk` (1-10): Grounded in exchange/venue/protocol health data.
- `complexity_risk` (1-10): Logic execution risk.
- `evidence_summary`: Traceable summary of findings from the acquired evidence.

Scores are deterministically aggregated into a weighted `total_risk_score` (Market 50%, Counterparty 25%, Complexity 25%).

### 3. Consequential Approval Outcome Preservation
A core requirement of capital-allocation safety is that validator tolerance must **never allow independently produced risk scores to disagree on whether a strategy crosses the approval threshold**.
- Approval threshold: `total_risk_score <= 550` (out of 1000).
- In Quantyra's `validator_fn`:
  ```python
  leader_approved = bool(leader.get("approved"))
  own_approved = bool(own.get("approved"))
  if leader_approved != own_approved:
      return False  # Strict preservation of consequential approval outcome
  ```
- If leader and validator agree on the consequential outcome (`APPROVED` vs `REJECTED`), a bounded tolerance of `MAX_METRIC_DEVIATION <= 2` across individual vectors is accepted for rationales and score rounding.

## State Lifecycle & Reuse Interface

Quantyra maintains:
1. `strategies: TreeMap[u256, Strategy]` with strict lifecycle transitions (`PENDING` -> `APPROVED` | `REJECTED`).
2. `risk_profiles: TreeMap[u256, RiskProfile]` containing the on-chain audit trail of acquired evidence URLs, evidence summaries, weighted scores, and rationales.

### Downstream Consumption
External DeFi vaults, DAOs, and automated allocators consume the contract via:
```python
is_approved(strategy_id) -> bool
get_strategy(strategy_id) -> dict
```
Capital deposits or trade execution can be conditionally locked until `is_approved(strategy_id)` returns `True`.

## Test Coverage

The repository includes invariant verification tests in `tests/test_quantyra.py`, validating:
- Deterministic URL and leverage limits.
- Bounded risk aggregation arithmetic.
- Strict rejection whenever leader and validator disagree across the consequential approval boundary.
