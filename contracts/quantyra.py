# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import genlayer as gl
from genlayer import *

import json
from dataclasses import dataclass


@allow_storage
@dataclass
class StrategyInput:
    name: str
    asset_class: str
    max_leverage: u32
    expected_drawdown_bps: u32
    logic_description: str

@allow_storage
@dataclass
class Strategy:
    id: u256
    owner: Address
    inputs: StrategyInput
    status: u8  # 0: PENDING, 1: APPROVED, 2: REJECTED

@allow_storage
@dataclass
class RiskProfile:
    market_risk: u8
    counterparty_risk: u8
    complexity_risk: u8
    total_risk_score: u32
    rationale: str

STATUS_PENDING = 0
STATUS_APPROVED = 1
STATUS_REJECTED = 2

@gl.contract_interface
class IQuantyra:
    class View:
        def get_strategy(self, strategy_id: u256) -> dict: ...
        def is_approved(self, strategy_id: u256) -> bool: ...

    class Write:
        def register_strategy(self, name: str, asset_class: str, max_leverage: int, expected_drawdown_bps: int, logic_description: str) -> u256: ...
        def evaluate_strategy(self, strategy_id: u256) -> None: ...

class Quantyra(gl.Contract):
    """Decentralized Risk Oracle and Gateway for Quantitative Trading Strategies."""

    strategies: TreeMap[u256, Strategy]
    risk_profiles: TreeMap[u256, RiskProfile]
    next_strategy_id: u256

    def __init__(self):
        self.next_strategy_id = u256(1)

    @gl.public.write
    def register_strategy(
        self, 
        name: str, 
        asset_class: str, 
        max_leverage: int, 
        expected_drawdown_bps: int, 
        logic_description: str
    ) -> u256:
        """
        Registers a new strategy with structured inputs and deterministic pre-validation.
        """
        # 1. Structured validation
        if not name or len(name) > 100:
            raise gl.vm.UserError("Invalid name length")
        if asset_class not in ["CRYPTO", "EQUITIES", "FOREX", "COMMODITIES"]:
            raise gl.vm.UserError("Unsupported asset class. Must be CRYPTO, EQUITIES, FOREX, or COMMODITIES.")
        if max_leverage < 1 or max_leverage > 100:
            raise gl.vm.UserError("Invalid leverage (must be 1-100)")
        if expected_drawdown_bps < 0 or expected_drawdown_bps > 10000:
            raise gl.vm.UserError("Invalid drawdown bps (must be 0-10000)")
        if not logic_description or len(logic_description) > 5000:
            raise gl.vm.UserError("Invalid logic description")

        # 2. Domain deterministic risk checks (pre-filter)
        if asset_class == "CRYPTO" and max_leverage > 10:
            raise gl.vm.UserError("Crypto leverage cannot exceed 10x")
        if expected_drawdown_bps > 5000:
            raise gl.vm.UserError("Strategies with >50% expected drawdown are automatically rejected.")

        sid = self.next_strategy_id
        self.next_strategy_id = u256(int(sid) + 1)
        
        inputs = StrategyInput(name, asset_class, u32(max_leverage), u32(expected_drawdown_bps), logic_description)
        strategy = self.strategies.get_or_insert_default(sid)
        strategy.id = sid
        strategy.owner = gl.message.sender_address
        strategy.inputs = inputs
        strategy.status = u8(STATUS_PENDING)
        
        return sid

    @gl.public.write
    def evaluate_strategy(self, strategy_id: u256) -> None:
        """
        Uses GenLayer's Equivalence Principle to evaluate strategy risks non-deterministically,
        then applies deterministic domain risk aggregation to approve or reject.
        """
        strategy = self.strategies.get(strategy_id)
        if strategy is None:
            raise gl.vm.UserError("Strategy not found")
        if strategy.status != u8(STATUS_PENDING):
            raise gl.vm.UserError("Strategy is not pending evaluation")

        inputs = strategy.inputs
        
        prompt = f"""
        You are a quantitative finance expert risk assessor.
        Analyze the following trading strategy and rate its risks on a scale of 1 to 10 (1=Safest, 10=Most Risky).
        
        Name: {inputs.name}
        Asset Class: {inputs.asset_class}
        Max Leverage: {int(inputs.max_leverage)}x
        Expected Drawdown: {int(inputs.expected_drawdown_bps) / 100}%
        Logic: {inputs.logic_description}
        
        Provide your assessment as a JSON object with EXACTLY these keys:
        - "market_risk": (integer 1-10) risk of market direction going against the strategy.
        - "counterparty_risk": (integer 1-10) risk of exchange/protocol failure.
        - "complexity_risk": (integer 1-10) risk of execution failure due to complex logic.
        - "rationale": a short explanation of your scores.
        """
        
        result = self._get_consensus(prompt)
        
        if result.get("error"):
            strategy.status = u8(STATUS_REJECTED)
            return

        mr = int(result["market_risk"])
        cr = int(result["counterparty_risk"])
        cxr = int(result["complexity_risk"])
        
        # 3. Explicit domain risk aggregation (Weighted average * 100 for integer math)
        # Market Risk (50%), Counterparty (20%), Complexity (30%)
        total_risk_score = (mr * 50) + (cr * 20) + (cxr * 30)
        
        profile = self.risk_profiles.get_or_insert_default(strategy_id)
        profile.market_risk = u8(mr)
        profile.counterparty_risk = u8(cr)
        profile.complexity_risk = u8(cxr)
        profile.total_risk_score = u32(total_risk_score)
        profile.rationale = result["rationale"]
        
        # 4. Meaningful Decision Control (State Lifecycle)
        # A score > 600 (out of 1000) is considered too risky to approve.
        if total_risk_score <= 600:
            strategy.status = u8(STATUS_APPROVED)
        else:
            strategy.status = u8(STATUS_REJECTED)

    @gl.public.view
    def get_strategy(self, strategy_id: u256) -> dict:
        strategy = self.strategies.get(strategy_id)
        if strategy is None:
            raise gl.vm.UserError("Strategy not found")
            
        result_dict = {
            "id": int(strategy.id),
            "owner": str(strategy.owner),
            "status": int(strategy.status),
            "inputs": {
                "name": strategy.inputs.name,
                "asset_class": strategy.inputs.asset_class,
                "max_leverage": int(strategy.inputs.max_leverage),
                "expected_drawdown_bps": int(strategy.inputs.expected_drawdown_bps),
                "logic_description": strategy.inputs.logic_description
            }
        }

        rp = self.risk_profiles.get(strategy_id)
        if rp is not None:
            result_dict["risk_profile"] = {
                "market_risk": int(rp.market_risk),
                "counterparty_risk": int(rp.counterparty_risk),
                "complexity_risk": int(rp.complexity_risk),
                "total_risk_score": int(rp.total_risk_score),
                "rationale": rp.rationale
            }
            
        return result_dict

    @gl.public.view
    def is_approved(self, strategy_id: u256) -> bool:
        """Reusable decision gate for downstream contracts (e.g. trading vaults)."""
        strategy = self.strategies.get(strategy_id)
        if strategy is None:
            return False
        return strategy.status == u8(STATUS_APPROVED)

    def _get_consensus(self, prompt: str) -> dict:
        def leader_fn() -> dict:
            try:
                raw = gl.nondet.exec_prompt(prompt, response_format="json")
                if isinstance(raw, str):
                    raw = json.loads(raw)
                
                # Robust output handling
                mr = int(raw.get("market_risk", 10))
                cr = int(raw.get("counterparty_risk", 10))
                cxr = int(raw.get("complexity_risk", 10))
                
                # Cap between 1 and 10
                mr = max(1, min(10, mr))
                cr = max(1, min(10, cr))
                cxr = max(1, min(10, cxr))
                
                return {
                    "market_risk": mr,
                    "counterparty_risk": cr,
                    "complexity_risk": cxr,
                    "rationale": str(raw.get("rationale", "No rationale"))
                }
            except Exception:
                return {"error": True}

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader = leader_result.calldata
            if not isinstance(leader, dict):
                return False
            if leader.get("error"):
                return True # Agree on failure
                
            own_result = leader_fn()
            if own_result.get("error"):
                return False
                
            # Equivalence Principle:
            # Validators accept the leader's exact rationale if the subjective risk scores 
            # are mathematically close (sum of absolute differences <= 2).
            diff_mr = abs(leader["market_risk"] - own_result["market_risk"])
            diff_cr = abs(leader["counterparty_risk"] - own_result["counterparty_risk"])
            diff_cxr = abs(leader["complexity_risk"] - own_result["complexity_risk"])
            
            total_diff = diff_mr + diff_cr + diff_cxr
            return total_diff <= 2

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        if isinstance(result, dict):
            return result
        return {"error": True}
