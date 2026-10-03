# Quantyra — Intelligent Contract Submission Notes

## Category

Standalone GenLayer Intelligent Contract / reusable primitive.

**No frontend. No backend. No mock product state.** The Intelligent Contract is the source of truth.

## One-line purpose

Quantyra is a Decentralized Quantitative Strategy Risk Oracle that uses deterministic validation and GenLayer's Equivalence Principle to evaluate and approve trading strategies for downstream DeFi consumption.

## Why this needs GenLayer

Syntax, leverage limits, expected drawdowns, state lifecycles, and risk aggregations are deterministic.
The hard part is subjective semantic risk evaluation:

- Does this trading strategy use excessive implicit leverage?
- Are the indicators overfitted to a specific market condition?
- What is the counterparty risk of the chosen asset class?

A conventional smart contract cannot resolve these questions from natural-language descriptions. A centralized AI service could, but then the risk oracle would inherit that centralized service's authority, introducing a single point of failure and bias.

Quantyra uses GenLayer consensus purely for the nondeterministic parts (the LLM-based risk vector assessment) while keeping the evaluation storage, structural validation, and aggregation strictly on-chain.

## Consensus design

### Structured Validation (Deterministic Pre-filter)
Before utilizing LLM resources, the contract rigorously validates structured inputs (`max_leverage`, `expected_drawdown_bps`) against hardcoded domain constraints. Violations result in immediate deterministic rejection.

### Strategy Processing
Quantyra uses GenLayer's non-deterministic `gl.nondet.exec_prompt` to ask the LLM to score the strategy across three vectors: Market, Counterparty, and Complexity (1-10 scale), along with a rationale. Output parsing handles missing keys and bounds checking robustly.

### Equivalence Principle & Decision Logic
Validators independently run the prompt. The Equivalence Principle allows them to reach consensus if their independent mathematical risk scores are mathematically close (sum of absolute differences across all three vectors <= 2). If validators agree, they accept the exact wording of the rationale proposed by the leader. 

The contract then deterministically aggregates these scores into a weighted `total_risk_score`. Strategies scoring below the threshold are advanced to `APPROVED`.

## Persistent state / primitive value

Quantyra maintains:
1. A registry of evaluated trading strategies with strict `PENDING`, `APPROVED`, or `REJECTED` state transitions.
2. A transparent record of the original strategy description mapped directly to its GenLayer consensus-backed risk profile.

Downstream contracts or DAOs can consume this primitive directly. For instance, a DAO smart contract could automatically approve funding for a trading bot only if `is_approved(id)` returns `True`.

## Test coverage

The repository contains Direct Mode tests for the basic integration structure.
