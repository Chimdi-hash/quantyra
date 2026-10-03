# Quantyra

**A Decentralized Quantitative Strategy Risk Oracle on GenLayer.**

Quantyra is a standalone Intelligent Contract primitive built for the GenLayer ecosystem. It evaluates quantitative trading strategies using real GenLayer consensus logic and Optimistic Democracy. 

## The Problem

Decentralized finance (DeFi) platforms and automated trading vaults need a way to reliably assess the risk of a proposed trading strategy before allocating capital. Traditional smart contracts cannot understand complex natural language strategies or nuanced risk profiles.

## The GenLayer Solution

Quantyra leverages GenLayer's **Optimistic Democracy** to securely process subjective assessments alongside deterministic risk limits:

1. **Structured Inputs & Deterministic Validation**: Strategies are submitted with explicit attributes (`asset_class`, `max_leverage`, `expected_drawdown_bps`). Quantyra enforces strict deterministic limits (e.g., rejecting crypto strategies with >10x leverage instantly) before any LLM execution.
2. **Intelligent Processing**: Quantyra uses GenLayer's non-deterministic `gl.nondet.exec_prompt` to ask the LLM to evaluate the strategy across three vectors: Market Risk, Counterparty Risk, and Complexity Risk.
3. **Equivalence Principle & Aggregation**: Validators independently run the prompt. The Equivalence Principle allows them to reach consensus if their independent mathematical risk scores are within an acceptable variance margin (sum of absolute differences <= 2). The contract then deterministically aggregates these scores into a weighted `total_risk_score`.
4. **Meaningful Decision Lifecycle**: If the `total_risk_score` is below a safe threshold, the strategy transitions to `APPROVED`. Other smart contracts and DeFi protocols can directly consume the `is_approved(id)` interface as a risk gate.

## Project Structure

- `contracts/quantyra.py`: The Intelligent Contract implementation containing the consensus logic.
- `tests/test_quantyra.py`: Basic test structures demonstrating how the contract integrates with testing frameworks.

## Why this is a Strong Primitive

- **Real Consensus Logic**: Utilizes `gl.vm.run_nondet_unsafe` for customized leader and validator consensus flows.
- **Equivalence Principle in Action**: Demonstrates exactly how to abstract subjective language variations while enforcing strict mathematical bounds on the variance of validator evaluations.
- **Decision Controls**: Features a meaningful state lifecycle (`PENDING`, `APPROVED`, `REJECTED`) that acts as a robust gatekeeper for external protocols.

## Deployment

**Contract Address (GenLayer Studio):** `0x0546EB1Cc852BC56C7D7Eb268d13b6C3D8B2Ab44`

**Explorer Link:** [https://explorer-studio.genlayer.com/address/0x0546EB1Cc852BC56C7D7Eb268d13b6C3D8B2Ab44](https://explorer-studio.genlayer.com/address/0x0546EB1Cc852BC56C7D7Eb268d13b6C3D8B2Ab44)
