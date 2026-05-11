"""
Optimized prompt templates for LLM interactions.
Designed for minimal token usage while maximizing actionable output.
"""

import json


class PromptTemplates:
    """Prompt templates for LLM-guided verification optimization."""

    SYSTEM_PROMPT = (
        "You are an IC verification optimization engine. "
        "Given coverage data from an 8-bit ALU UVM testbench, "
        "suggest optimal random seeds and stimulus strategies to close coverage gaps. "
        "The ALU has 6 operations (ADD=0,SUB=1,MUL=2,DIV=3,AND=4,XOR=5), "
        "8-bit operands A/B, carry-in C_in, and Reset. "
        "Coverage tracks: individual operand values (0x00, 0xFF), "
        "all 6 opcodes, and 12 corner-case cross bins "
        "(each opcode with both operands at 0x00 or 0xFF). "
        "Respond in JSON only. Minimize token usage."
    )

    @staticmethod
    def seed_strategy_prompt(coverage_data: dict) -> str:
        """Generate seed strategy prompt from coverage data."""
        compact = {
            "cov": round(coverage_data.get("coverage", 0), 1),
            "gaps": coverage_data.get("uncovered_bins", [])[:8],
            "trend": [round(x, 1) for x in coverage_data.get("trend", [])[-5:]],
        }
        return (
            f"Coverage state: {json.dumps(compact, separators=(',', ':'))}\n"
            "Suggest 3-5 seeds (1-100000) and strategy. "
            'JSON format: {"seeds":[int],"strategy":"str","bias":{"A_weight_ff":int,"B_weight_00":int,"opcode_focus":[int]}}'
        )

    @staticmethod
    def gap_analysis_prompt(gaps: list) -> str:
        """Generate gap analysis prompt."""
        gap_summary = [
            {"cp": g.get("coverpoint", ""), "bin": g.get("bin", ""), "h": g.get("hits", 0)}
            for g in gaps[:10]
        ]
        return (
            f"Uncovered bins: {json.dumps(gap_summary, separators=(',', ':'))}\n"
            "Which seeds/patterns would hit these? "
            'JSON: {"target_patterns":[{"A":int,"B":int,"op":int}],"seed_hints":[int]}'
        )

    @staticmethod
    def constraint_prompt(state: dict) -> str:
        """Generate constraint adjustment prompt."""
        compact = {
            "cov": round(state.get("coverage", 0), 1),
            "iter": state.get("iteration", 0),
            "stagnant": state.get("stagnation", False),
            "uncov": state.get("uncovered_count", 0),
        }
        return (
            f"State: {json.dumps(compact, separators=(',', ':'))}\n"
            "Suggest constraint weight adjustments for A,B distributions "
            "and opcode selection to maximize coverage. "
            'JSON: {"A_dist":{"ff":int,"00":int,"mid":int},"B_dist":{"ff":int,"00":int,"mid":int},"op_weights":[int]*6}'
        )

    @staticmethod
    def redundancy_check_prompt(test_history: list) -> str:
        """Ask LLM to identify redundant tests."""
        compact = [
            {"seed": t.get("seed"), "cov_delta": round(t.get("coverage_delta", 0), 2)}
            for t in test_history[-20:]
        ]
        return (
            f"Test history: {json.dumps(compact, separators=(',', ':'))}\n"
            "Identify redundant seeds (cov_delta near 0) and suggest "
            "which to skip in future regressions. "
            'JSON: {"redundant_seeds":[int],"essential_seeds":[int],"reason":"str"}'
        )
