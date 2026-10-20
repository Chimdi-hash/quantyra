# Quantyra

**Decentralized Strategy Risk Gateway on GenLayer.**

Quantyra is a standalone GenLayer Intelligent Contract primitive that evaluates capital-allocation risk for quantitative trading strategies. It grounds risk assessments directly in contract-acquired market and counterparty evidence, while enforcing strict preservation of consequential approval outcomes under GenLayer's Optimistic Democracy.

## The Problem

Decentralized finance (DeFi) platforms, autonomous agents, and automated trading vaults need a reliable way to assess the risk of a proposed trading strategy before allocating capital. Traditional smart contracts cannot acquire and reason over unstructured market feeds, counterparty health metrics, or natural-language strategy descriptions. Meanwhile, off-chain AI services introduce centralized points of failure and lack verifiable on-chain consensus.

## The GenLayer Solution

Quantyra combines deterministic pre-filters with GenLayer's non-deterministic web rendering and LLM execution to create an auditable, decentralized risk gateway:

1. **Structured Strategy Inputs & Deterministic Pre-Filters**: Strategies register with strict specifications (`asset_class`, `target_asset`, `max_leverage`, `expected_drawdown_bps`, `evidence_url`, `logic_description`). The contract deterministically enforces safety envelopes (e.g., maximum 10x leverage for Crypto/DeFi, max 50% drawdown) before any non-deterministic compute is spent.
2. **Contract-Acquired Market & Counterparty Evidence**: The contract does not make capital-allocation decisions in a vacuum. During evaluation, leader and validators independently fetch live market telemetry and counterparty health evidence via `gl.nondet.web.render(evidence_url, mode="text")`. If evidence cannot be acquired or is empty, the contract fails closed to protect capital.
3. **Evidence-Grounded Risk Scoring**: The acquired evidence is injected directly into the LLM assessment prompt. The model evaluates three distinct risk vectors (Market Risk 50%, Counterparty Risk 25%, Complexity Risk 25%), producing bounded integer scores (1-10) and an evidence summary.
4. **Preservation of Consequential Approval Outcome via Independent Validator Binding**: A key innovation in Quantyra's Equivalence Principle implementation is that **validators independently bind the final approval outcome without trusting any leader-provided flag**. The validator recomputes the leader's outcome directly from the submitted risk fields (`market_risk`, `counterparty_risk`, `complexity_risk`) and compares that derived outcome against the validator's independently derived outcome. If they disagree on crossing the approval threshold, consensus strictly fails. Equivalence tolerance only applies when both agree on the consequential decision and variance across individual vectors is within `MAX_METRIC_DEVIATION <= 2`.
5. **Reusable Gate for External Protocols**: Strategies transition through an on-chain lifecycle (`PENDING` -> `APPROVED` | `REJECTED`). External vaults and DAOs query `is_approved(strategy_id)` to programmatically guard capital allocations.

## Architecture

```
[User/Vault] ---> register_strategy(inputs, evidence_url) ---> [PENDING]
                                                                   |
                                                          evaluate_strategy()
                                                                   |
       +-----------------------------------------------------------+-----------------------------------------------------------+
       | Leader Execution                                                                      | Validator Execution           |
       | 1. gl.nondet.web.render(evidence_url)                                                | 1. Independent web render     |
       | 2. gl.nondet.exec_prompt(strategy + live evidence)                                    | 2. Independent exec_prompt    |
       | 3. Submit risk fields (market, counterparty, complexity)                             | 3. Recompute leader outcome   |
       |                                                                                       |    & derive own outcome       |
       +-----------------------------------------------------------+-----------------------------------------------------------+
                                                                   |
                                              gl.vm.run_nondet_unsafe() Check:
                                              1. derived_leader_approved == derived_own_approved ? (STRICT BINDING)
                                              2. sum(abs(metric_diffs)) <= 2 ?
                                                                   |
                                           Passed ---> [APPROVED] (Vault deposits unlocked)
                                           Failed ---> [REJECTED] (Capital allocation blocked)
```

## Project Structure

- `contracts/quantyra.py`: The Intelligent Contract implementation containing evidence acquisition, equivalence consensus, and approval controls.
- `tests/test_quantyra.py`: Invariant verification tests for approval boundary preservation and deterministic bounds.
- `SUBMISSION.md`: Detailed submission documentation and architectural notes.
- `gltest.config.yaml`: Test harness configuration for localnet and studionet.
- `requirements-test.txt`: Testing dependencies (`genlayer-test`).

## Deployment

**Contract Address (GenLayer Studio):** `0xDC7d1AbA97fEE0b60034425B6faa2837e7E69f56`

**Explorer Link:** [https://explorer-studio.genlayer.com/address/0xDC7d1AbA97fEE0b60034425B6faa2837e7E69f56](https://explorer-studio.genlayer.com/address/0xDC7d1AbA97fEE0b60034425B6faa2837e7E69f56)
