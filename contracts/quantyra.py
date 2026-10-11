# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import genlayer as gl
from genlayer import *

import json
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants & Domain Risk Limits
# ---------------------------------------------------------------------------

MAX_NAME_LEN = 96
MAX_ASSET_LEN = 32
MAX_URL_LEN = 512
MAX_LOGIC_LEN = 5000
MAX_EVIDENCE_SNIPPET_LEN = 3000

STATUS_PENDING = 0
STATUS_APPROVED = 1
STATUS_REJECTED = 2

# Risk aggregation weights (sum = 100)
# Market Risk: 50%, Counterparty Risk: 25%, Complexity Risk: 25%
WEIGHT_MARKET = 50
WEIGHT_COUNTERPARTY = 25
WEIGHT_COMPLEXITY = 25

# Approval threshold: Total weighted risk score must be <= 550 out of 1000 (i.e. <= 5.5 / 10)
APPROVAL_MAX_RISK_SCORE = 550

# Maximum permitted aggregate metric variance between leader and validator
MAX_METRIC_DEVIATION = 2


# ---------------------------------------------------------------------------
# Deterministic Domain Helpers
# ---------------------------------------------------------------------------

def validate_https_url(url: str) -> str:
    cleaned = str(url).strip()
    if len(cleaned) == 0 or len(cleaned) > MAX_URL_LEN:
        raise gl.vm.UserError(f"Evidence URL must be between 1 and {MAX_URL_LEN} characters.")
    if not cleaned.startswith("https://"):
        raise gl.vm.UserError("Evidence URL must start with https://")
    return cleaned


def compute_total_risk_score(mr: int, cr: int, cxr: int) -> int:
    return (mr * WEIGHT_MARKET) + (cr * WEIGHT_COUNTERPARTY) + (cxr * WEIGHT_COMPLEXITY)


def is_consequentially_approved(total_score: int) -> bool:
    return total_score <= APPROVAL_MAX_RISK_SCORE


# ---------------------------------------------------------------------------
# Storage Models
# ---------------------------------------------------------------------------

@allow_storage
@dataclass
class StrategyInput:
    name: str
    asset_class: str
    target_asset: str
    max_leverage: u32
    expected_drawdown_bps: u32
    evidence_url: str
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
    evidence_url: str
    evidence_summary: str
    rationale: str


# ---------------------------------------------------------------------------
# Public Contract Interface
# ---------------------------------------------------------------------------

@gl.contract_interface
class IQuantyra:
    class View:
        def get_strategy(self, strategy_id: u256) -> dict: ...
        def is_approved(self, strategy_id: u256) -> bool: ...

    class Write:
        def register_strategy(
            self,
            name: str,
            asset_class: str,
            target_asset: str,
            max_leverage: int,
            expected_drawdown_bps: int,
            evidence_url: str,
            logic_description: str,
        ) -> u256: ...
        def evaluate_strategy(self, strategy_id: u256) -> None: ...


# ---------------------------------------------------------------------------
# Intelligent Contract Implementation
# ---------------------------------------------------------------------------

class Quantyra(gl.Contract):
    """
    Decentralized Quantitative Strategy Risk Gateway.

    Grounds capital-allocation risk assessment in contract-acquired market & counterparty
    evidence, and strictly preserves consequential approval outcomes under GenLayer consensus.
    """

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
        target_asset: str,
        max_leverage: int,
        expected_drawdown_bps: int,
        evidence_url: str,
        logic_description: str,
    ) -> u256:
        """
        Registers a new strategy with structured inputs and deterministic pre-validation.
        Enforces asset-class specific leverage bounds and evidence URL provenance.
        """
        # 1. Structural input validation
        cleaned_name = str(name).strip()
        if len(cleaned_name) == 0 or len(cleaned_name) > MAX_NAME_LEN:
            raise gl.vm.UserError(f"Name must be 1..{MAX_NAME_LEN} characters.")

        cleaned_class = str(asset_class).strip().upper()
        if cleaned_class not in ["CRYPTO", "EQUITIES", "FOREX", "COMMODITIES", "DEFI"]:
            raise gl.vm.UserError("Unsupported asset class. Must be CRYPTO, EQUITIES, FOREX, COMMODITIES, or DEFI.")

        cleaned_asset = str(target_asset).strip()
        if len(cleaned_asset) == 0 or len(cleaned_asset) > MAX_ASSET_LEN:
            raise gl.vm.UserError(f"Target asset must be 1..{MAX_ASSET_LEN} characters.")

        if max_leverage < 1 or max_leverage > 100:
            raise gl.vm.UserError("Leverage must be between 1x and 100x.")

        if expected_drawdown_bps < 0 or expected_drawdown_bps > 10000:
            raise gl.vm.UserError("Drawdown basis points must be between 0 and 10000 (0-100%).")

        valid_evidence_url = validate_https_url(evidence_url)

        cleaned_logic = str(logic_description).strip()
        if len(cleaned_logic) == 0 or len(cleaned_logic) > MAX_LOGIC_LEN:
            raise gl.vm.UserError(f"Logic description must be 1..{MAX_LOGIC_LEN} characters.")

        # 2. Domain deterministic risk pre-filters
        if cleaned_class in ["CRYPTO", "DEFI"] and max_leverage > 10:
            raise gl.vm.UserError("Crypto and DeFi strategies cannot exceed 10x leverage.")

        if cleaned_class == "FOREX" and max_leverage > 50:
            raise gl.vm.UserError("Forex strategies cannot exceed 50x leverage.")

        if expected_drawdown_bps > 5000:
            raise gl.vm.UserError("Strategies with >50% expected drawdown are rejected deterministically.")

        # 3. Store strategy in PENDING state
        sid = self.next_strategy_id
        self.next_strategy_id = u256(int(sid) + 1)

        inputs = StrategyInput(
            name=cleaned_name,
            asset_class=cleaned_class,
            target_asset=cleaned_asset,
            max_leverage=u32(max_leverage),
            expected_drawdown_bps=u32(expected_drawdown_bps),
            evidence_url=valid_evidence_url,
            logic_description=cleaned_logic,
        )

        strat = self.strategies.get_or_insert_default(sid)
        strat.id = sid
        strat.owner = gl.message.sender_address
        strat.inputs = inputs
        strat.status = u8(STATUS_PENDING)

        return sid

    @gl.public.write
    def evaluate_strategy(self, strategy_id: u256) -> None:
        """
        Acquires current market and counterparty evidence, performs equivalence-bounded
        consensus assessment, and updates the strategy approval lifecycle.
        """
        strat = self.strategies.get(strategy_id)
        if strat is None:
            raise gl.vm.UserError("Strategy not found.")
        if strat.status != u8(STATUS_PENDING):
            raise gl.vm.UserError("Strategy is not in PENDING status.")

        inputs = strat.inputs
        result = self._evaluate_consensus(inputs)

        # Fail-closed handling if evidence acquisition or consensus failed
        if result.get("error"):
            strat.status = u8(STATUS_REJECTED)
            profile = self.risk_profiles.get_or_insert_default(strategy_id)
            profile.market_risk = u8(10)
            profile.counterparty_risk = u8(10)
            profile.complexity_risk = u8(10)
            profile.total_risk_score = u32(1000)
            profile.evidence_url = inputs.evidence_url
            profile.evidence_summary = "Evidence acquisition failed or was rejected by consensus."
            profile.rationale = str(result.get("reason", "Evaluation failed."))
            return

        mr = int(result["market_risk"])
        cr = int(result["counterparty_risk"])
        cxr = int(result["complexity_risk"])
        total_risk_score = compute_total_risk_score(mr, cr, cxr)

        profile = self.risk_profiles.get_or_insert_default(strategy_id)
        profile.market_risk = u8(mr)
        profile.counterparty_risk = u8(cr)
        profile.complexity_risk = u8(cxr)
        profile.total_risk_score = u32(total_risk_score)
        profile.evidence_url = inputs.evidence_url
        profile.evidence_summary = str(result.get("evidence_summary", ""))
        profile.rationale = str(result.get("rationale", ""))

        # Exact consequential outcome assignment
        if is_consequentially_approved(total_risk_score):
            strat.status = u8(STATUS_APPROVED)
        else:
            strat.status = u8(STATUS_REJECTED)

    @gl.public.view
    def get_strategy(self, strategy_id: u256) -> dict:
        strat = self.strategies.get(strategy_id)
        if strat is None:
            raise gl.vm.UserError("Strategy not found.")

        status_code = int(strat.status)
        status_label = "PENDING"
        if status_code == STATUS_APPROVED:
            status_label = "APPROVED"
        elif status_code == STATUS_REJECTED:
            status_label = "REJECTED"

        result = {
            "id": int(strat.id),
            "owner": str(strat.owner),
            "status": status_code,
            "status_label": status_label,
            "inputs": {
                "name": strat.inputs.name,
                "asset_class": strat.inputs.asset_class,
                "target_asset": strat.inputs.target_asset,
                "max_leverage": int(strat.inputs.max_leverage),
                "expected_drawdown_bps": int(strat.inputs.expected_drawdown_bps),
                "evidence_url": strat.inputs.evidence_url,
                "logic_description": strat.inputs.logic_description,
            },
        }

        rp = self.risk_profiles.get(strategy_id)
        if rp is not None:
            result["risk_profile"] = {
                "market_risk": int(rp.market_risk),
                "counterparty_risk": int(rp.counterparty_risk),
                "complexity_risk": int(rp.complexity_risk),
                "total_risk_score": int(rp.total_risk_score),
                "evidence_url": rp.evidence_url,
                "evidence_summary": rp.evidence_summary,
                "rationale": rp.rationale,
            }

        return result

    @gl.public.view
    def is_approved(self, strategy_id: u256) -> bool:
        """
        Reusable gate for external DeFi vaults and capital allocation contracts.
        """
        strat = self.strategies.get(strategy_id)
        if strat is None:
            return False
        return strat.status == u8(STATUS_APPROVED)

    # ------------------------------------------------------------------
    # Consensus Engine: Contract-Acquired Evidence & Consequential Preservation
    # ------------------------------------------------------------------

    def _evaluate_consensus(self, inputs: StrategyInput) -> dict:
        def evaluate_once() -> dict:
            # Step 1: Ground assessment in contract-acquired market & counterparty evidence
            evidence_text = ""
            try:
                page = gl.nondet.web.render(inputs.evidence_url, mode="text")
                raw_evidence = str(page).strip()
                if len(raw_evidence) > MAX_EVIDENCE_SNIPPET_LEN:
                    evidence_text = raw_evidence[:MAX_EVIDENCE_SNIPPET_LEN]
                else:
                    evidence_text = raw_evidence
            except Exception as exc:
                return {
                    "error": True,
                    "reason": f"Contract failed to acquire evidence: {str(exc)[:100]}",
                }

            if len(evidence_text) == 0:
                return {
                    "error": True,
                    "reason": "Acquired market/counterparty evidence was empty.",
                }

            # Step 2: Intelligent risk evaluation prompt grounded in acquired evidence
            prompt = f"""
You are an expert quantitative risk assessor reviewing a capital allocation request for an automated trading vault.
Analyze the proposed strategy against the CURRENT MARKET AND COUNTERPARTY EVIDENCE ACQUIRED BY THE CONTRACT:

[STRATEGY SPECIFICATION]
Name: {inputs.name}
Asset Class: {inputs.asset_class}
Target Asset: {inputs.target_asset}
Maximum Leverage: {int(inputs.max_leverage)}x
Expected Maximum Drawdown: {int(inputs.expected_drawdown_bps) / 100}%
Strategy Logic: {inputs.logic_description}

[CONTRACT-ACQUIRED MARKET & COUNTERPARTY EVIDENCE]
Source URL: {inputs.evidence_url}
Live Telemetry / Evidence Data:
{evidence_text}

[EVALUATION REQUIREMENTS]
Evaluate the strategy risks grounded directly in the acquired evidence above:
1. Market Risk (1-10): Given current volatility and liquidity shown in the evidence, rate the market downside risk.
2. Counterparty Risk (1-10): Given exchange/venue/protocol health shown in the evidence, rate counterparty insolvency or outage risk.
3. Complexity Risk (1-10): Rate logic flaw or execution divergence risk.

Respond in JSON format with EXACTLY these keys:
- "market_risk": (integer between 1 and 10)
- "counterparty_risk": (integer between 1 and 10)
- "complexity_risk": (integer between 1 and 10)
- "evidence_summary": (1-2 sentences summarizing how the acquired evidence informed the assessment)
- "rationale": (short paragraph explaining the quantitative risk determination)
"""
            try:
                raw_response = gl.nondet.exec_prompt(prompt, response_format="json")
                if isinstance(raw_response, str):
                    parsed = json.loads(raw_response)
                elif isinstance(raw_response, dict):
                    parsed = raw_response
                else:
                    return {"error": True, "reason": "Invalid LLM response format."}

                mr = max(1, min(10, int(parsed.get("market_risk", 10))))
                cr = max(1, min(10, int(parsed.get("counterparty_risk", 10))))
                cxr = max(1, min(10, int(parsed.get("complexity_risk", 10))))

                ev_summary = str(parsed.get("evidence_summary", "Evidence verified."))[:300]
                rationale = str(parsed.get("rationale", "Standard risk evaluation completed."))[:500]

                total_score = compute_total_risk_score(mr, cr, cxr)
                approved = is_consequentially_approved(total_score)

                return {
                    "error": False,
                    "market_risk": mr,
                    "counterparty_risk": cr,
                    "complexity_risk": cxr,
                    "total_risk_score": total_score,
                    "approved": approved,
                    "evidence_summary": ev_summary,
                    "rationale": rationale,
                }
            except Exception as exc:
                return {"error": True, "reason": f"Evaluation parsing error: {str(exc)[:100]}"}

        def leader_fn() -> dict:
            return evaluate_once()

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader = leader_result.calldata
            if not isinstance(leader, dict):
                return False

            # If leader reported an error (e.g. evidence acquisition failure), validator must verify
            if leader.get("error"):
                own = evaluate_once()
                return own.get("error") is True

            own = evaluate_once()
            if own.get("error"):
                return False

            # ------------------------------------------------------------------
            # INVARIANT 1: PRESERVE EXACT CONSEQUENTIAL APPROVAL OUTCOME
            # ------------------------------------------------------------------
            # Validator tolerance CANNOT bridge a disagreement on crossing the
            # approval threshold. If leader and validator differ on approval, reject.
            leader_approved = bool(leader.get("approved"))
            own_approved = bool(own.get("approved"))
            if leader_approved != own_approved:
                return False

            # ------------------------------------------------------------------
            # INVARIANT 2: BOUNDED METRIC TOLERANCE
            # ------------------------------------------------------------------
            # If both agree on the consequential outcome, ensure individual
            # risk vector scores are mathematically close.
            diff_mr = abs(int(leader["market_risk"]) - int(own["market_risk"]))
            diff_cr = abs(int(leader["counterparty_risk"]) - int(own["counterparty_risk"]))
            diff_cxr = abs(int(leader["complexity_risk"]) - int(own["complexity_risk"]))
            total_dev = diff_mr + diff_cr + diff_cxr

            return total_dev <= MAX_METRIC_DEVIATION

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        if isinstance(result, dict):
            return result
        return {"error": True, "reason": "Consensus failed"}
