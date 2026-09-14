
from __future__ import annotations
import json
import re
import shlex
from pathlib import Path

"""This script created for the deterministic trajectory decision logic, which reads the judge's trajectory evaluation and decides whether to keep the trajectory for RL training"""

def compute_filter_label(te: dict) -> str:
    """Compute a filter label for the trajectory based on the judge's evaluation."""
    s = te.get("scores", {})
    ps = te.get("phase_signals", {})
    ss = te.get("signal_strength", {})

    vi = s.get("verifier_integrity", 3)
    er = s.get("environment_readiness", 3)
    dc = s.get("dependency_completeness", 3)
    lv = s.get("trajectory_progress_value", 3)
    solver_sig = ss.get("solver_signal", "weak")
    oracle_out = te.get("oracle_outcome", "unknown")

    # Hard rejects
    if vi == 1:
        return "reject"
    if er == 1 and dc == 1:
        return "reject"
    if oracle_out == "not_run" and solver_sig == "weak":
        return "reject"
    if vi <= 2 and solver_sig == "weak":
        return "reject"

    # Routing repairs
    # Three 1. Keep_verifier_repair based on repair_priority, 2. keep_instruction_update once we have instruction tuning advice, 3. downweight if solver made progress but verifier rejected it
    if (
        vi <= 2
        and ps.get("touched_relevant_files", False)
        and solver_sig in ("medium", "strong")
    ):
        return "keep_verifier_repair"  # solver made progress; verifier rejected it

    if (
        te.get("needs_instruction_change", False)
        and not te.get("needs_verifier_change", False)
        and not ps.get("touched_relevant_files", False)
        and solver_sig != "weak"
    ):
        return "keep_instruction_update"

    # Clean keep
    if all(
        s.get(d, 0) >= 3
        for d in [
            "environment_readiness",
            "dependency_completeness",
            "verifier_integrity",
            "instruction_verifier_alignment",
        ]
    ):
        return "keep"

    # Downweight fallback
    if (vi + er + dc) / 3 >= 2.5 and solver_sig != "weak":
        return "downweight"

    return "reject"


def _check_score_consistency(te: dict) -> list[str]:
    """Warn if judge's reported scores deviate significantly from the deduction table."""
    DEDUCTIONS_MAT = {
        "bootstrap_blocked": [("environment_readiness", -2)],
        "activation_missing": [("environment_readiness", -1)],
        "missing_dependency": [("dependency_completeness", -1)],
        "wrong_test_target": [("verifier_integrity", -2)],
        "verifier_shortcut_risk": [("verifier_integrity", -3)],
        "non_discriminating_verifier": [("verifier_integrity", -3)],
        "instruction_verifier_mismatch": [("instruction_verifier_alignment", -2)],
        "instruction_underspecified": [("instruction_verifier_alignment", -1)],
    }
    expected = {
        k: 4
        for k in [
            "environment_readiness",
            "dependency_completeness",
            "verifier_integrity",
            "instruction_verifier_alignment",
        ]
    }
    for sp in te.get("struggle_patterns", []):
        pattern_name = sp.get("pattern", "") if isinstance(sp, dict) else str(sp)
        for dim, delta in DEDUCTIONS_MAT.get(pattern_name, []):
            expected[dim] = max(1, expected[dim] + delta)

    reported = te.get("scores", {})
    return [
        f"{dim}: expected ~{exp}, judge reported {reported.get(dim)}"
        for dim, exp in expected.items()
        if reported.get(dim) is not None and abs(reported[dim] - exp) > 1
    ]


def compute_trajectory_decision(te: dict) -> dict:
    """Compute the trajectory decision based on the trajectory evaluation."""
    fl = compute_filter_label(te)
    s = te.get("scores", {})

    keep_for_rl = {
        "keep": "keep",
        "keep_verifier_repair": "keep",
        "keep_instruction_update": "keep",
        "downweight": "downweight",
        "reject": "reject",
    }.get(fl, "downweight")

    overall = round(
        sum(
            s.get(d, 3)
            for d in [
                "environment_readiness",
                "dependency_completeness",
                "verifier_integrity",
                "instruction_verifier_alignment",
            ]
        )
        / 4,
        2,
    )

    ita = te.get("instruction_tuning_advice", {})
    patterns = te.get("struggle_patterns", [])
    sp_names = [(p.get("pattern") if isinstance(p, dict) else str(p)) for p in patterns]
    warnings = _check_score_consistency(te)

    return {
        "schema_version": "v1",
        "filter_label": fl,
        "keep_for_rl": keep_for_rl,
        "is_good_rl_example": fl not in ("downweight", "reject"),
        "overall_score": overall,
        "primary_scores": {
            k: s[k]
            for k in [
                "environment_readiness",
                "dependency_completeness",
                "verifier_integrity",
                "instruction_verifier_alignment",
                "trajectory_progress_value",
            ]
            if k in s
        },
        "dominant_struggle_patterns": sp_names[:5],
        "needs_instruction_tuning": (
            ita.get("priority") in ("medium", "high")
            and te.get("needs_instruction_change", False)
            and not te.get("needs_verifier_change", False)
        ),
        "needs_verifier_repair": te.get("needs_verifier_change", False),
        "score_warnings": warnings,
        "decision_source": "computed",
    }


# Any Hints
IMPL_HINT_RE = re.compile(
    r"\b(use|call|edit|modify|add|remove|replace|change)\b"
    r".{0,80}\b(function|method|class|line|file|variable|switch|regex|if\s+statement)\b",
    re.IGNORECASE,
)
VERIFIER_LEAK_RE = re.compile(
    r"\b(eval\.sh|oracle verifier|hidden test|test\.patch|fix\.patch|"
    r"OPENENV_EXIT_CODE|trajectory judge)\b",
    re.IGNORECASE,
)

def candidate_instruction_safety(
    original: str, candidate: str
) -> dict:
    reasons = []
     
    added_words = max(0, len(candidate.split()) - len(original.split()))
    if IMPL_HINT_RE.search(candidate):
        reasons.append("implementation_specificity")
    if VERIFIER_LEAK_RE.search(candidate):
        reasons.append("verifier_or_patch_leakage")

    return {
        "accepted": not reasons,
        "impl_specific": bool(IMPL_HINT_RE.search(candidate)),
        "verifier_leak": bool(VERIFIER_LEAK_RE.search(candidate)),
        "added_words": added_words,
        "rejection_reasons": reasons,
    }


def build_instruction_request(
    issue_text: str,
    exploration_report: dict,
    te: dict,
) -> dict:
    ita = te.get("instruction_tuning_advice", {})
    return {
        "source_instruction_path": "/tasks/issue.md",
        "source_instruction": issue_text,
        "patch_behavior_summary": exploration_report.get("pr_summary", ""),
        "tuning_context": ita.get("tuning_context", ""),
        "missing_spec_type": ita.get("missing_spec_type", "none"),
        "max_candidates": 2,
        "max_added_sentences": 2,
        "rules": [
            "preserve the original instruction",
            "add behavioral clarification only",
            "do not describe implementation",
            "do not mention verifier, oracle, tests, or patch internals",
            "do not make the task easier by revealing the solution",
        ],
    }
