---
name: trajectory-rubric-spec
description: Provide the trajectory evaluation for the agent trajectories run upon the workspace — v2.0 causal rubric
---

# OpenEnv Trajectory Rubric — v2.0

The judge uses two evidence channels:
- solver trajectory evidence
- oracle verifier log evidence

**Causal rule**: identify struggle patterns FIRST, then derive scores FROM those patterns. Do not score dimensions independently. Every score below 4 must map to at least one struggle pattern.

## Score scale (1–5)

- `1`: broken / reject-level
- `2`: weak / likely downweight or repair needed
- `3`: usable but mixed
- `4`: strong
- `5`: excellent

## Primary scores (derive from struggle patterns)

Start all at **4**. Apply deductions from the table below. Clamp to [1, 5].

| Score | What it measures |
|-------|-----------------|
| `environment_readiness` | Whether the built environment was usable for the solver |
| `dependency_completeness` | Whether required dependencies were present or recoverable |
| `verifier_integrity` | Whether the verifier was fair, targeted, and free of shortcuts based on verifier run log and verifier script |
| `instruction_verifier_alignment` | Whether the instruction and oracle verifier judge the same thing |
| `trajectory_progress_value` | Whether this trajectory has any progress |

**`trajectory_progress_value` is NOT free-scored.** Derive it:
- If `verifier_integrity == 1` → force to 1
- If `environment_readiness == 1 AND dependency_completeness == 1` → force to 1
- If `solver_signal == "weak" AND oracle_signal == "weak"` → cap at 2
- Otherwise: keep as derived from deductions

## Struggle pattern enum

```
bootstrap_blocked            activation_missing           missing_dependency
test_never_ran               wrong_test_target            verifier_shortcut_risk
non_discriminating_verifier  oracle_failure_non_actionable
instruction_verifier_mismatch  instruction_underspecified
solver_oracle_disagreement   problem_not_localized        search_without_edit
repeated_same_error          patch_churn_without_progress
timeout_before_meaningful_fix  flaky_execution            none
```

## Struggle pattern → score deduction table

| Pattern | Dimension | Delta |
|---------|-----------|-------|
| `bootstrap_blocked` | `environment_readiness` | −2 |
| `activation_missing` | `environment_readiness` | −1 |
| `missing_dependency` | `dependency_completeness` | −1 |
| `test_never_ran` (runtime cause) | `dependency_completeness` | −1 |
| `test_never_ran` (verifier cause) | `verifier_integrity` | −2 |
| `wrong_test_target` | `verifier_integrity` | −2 |
| `verifier_shortcut_risk` | `verifier_integrity` | −3 |
| `non_discriminating_verifier` | `verifier_integrity` | −3 |
| `oracle_failure_non_actionable` | `verifier_integrity` | −1 |
| `instruction_verifier_mismatch` | `instruction_verifier_alignment` | −2 |
| `instruction_underspecified` | `instruction_verifier_alignment` | −1 |
| `solver_oracle_disagreement` (solver approach valid) | `verifier_integrity` −1, `instruction_verifier_alignment` −1 |
| `problem_not_localized` | `trajectory_progress_value` | −1 |
| `search_without_edit` | `trajectory_progress_value` | −2 |
| `repeated_same_error` | `trajectory_progress_value` | −1 |
| `patch_churn_without_progress` | `trajectory_progress_value` | −1 |
| `timeout_before_meaningful_fix` | context only — weakens `oracle_signal` weight; no direct deduction |

## Required JSON output schema (v2.0)

```json
{
  "schema_version": "2.0",
  "solver_outcome": "pass | fail | partial | timeout | error | unknown",
  "oracle_outcome": "pass | fail | not_run | inconclusive | error | unknown",
  "scores": {
    "environment_readiness": 4,
    "dependency_completeness": 4,
    "verifier_integrity": 4,
    "instruction_verifier_alignment": 4,
    "trajectory_progress_value": 4
  },
  "struggle_patterns": [
    {
      "pattern": "<enum value>",
      "phase": "bootstrap | exploration | edit | verification",
      "evidence": "one trajectory-grounded sentence",
      "score_impacts": [{"dimension": "verifier_integrity", "delta": -2}]
    }
  ],
  "phase_signals": {
    "tests_executed": false,
    "first_meaningful_edit_made": false,
    "touched_relevant_files": false,
    "solver_time_budget_exhausted": false,
    "oracle_verifier_executed": false,
    "oracle_verifier_passed": false
  },
  "signal_strength": {
    "solver_signal": "weak | medium | strong",
    "oracle_signal": "weak | medium | strong"
  },
  "verifier_diagnosis": {
    "verifier_coverage_class": "valid | behavioral | implementation_pattern | non_discriminating | shortcut_risk | unknown",
    "solver_approach_valid": false,
    "repair_priority": "none | low | medium | high"
  },
  "needs_verifier_change": false,
  "needs_instruction_change": false,
  "instruction_tuning_advice": {
    "priority": "none | low | medium | high",
    "missing_spec_type": "behavioral_outcome | scope_clarification | difficulty_framing | none",
    "tuning_context": "one sentence: what solver couldn't determine from the instruction",
    "anti_contamination_constraints": []
  },
  "filter_label": "keep | keep_verifier_repair | keep_instruction_update | downweight | reject",
  "summary": "max 3 sentences, trajectory-grounded",
  "evidence": ["at most 5 grounded facts from trajectory or oracle log and oracle verifier script"]
}
```

## `filter_label` derivation (advisory — Python overwrites with authoritative value)

```
Hard rejects:
  verifier_integrity == 1                                        → "reject"
  environment_readiness == 1 AND dependency_completeness == 1   → "reject"
  oracle_outcome == "not_run" AND solver_signal == "weak"        → "reject"
  verifier_integrity <= 2 AND solver_signal == "weak"            → "reject"

Routing repairs:
  verifier_integrity <= 2
    AND phase_signals.touched_relevant_files == true
    AND solver_signal in ("medium", "strong")                    → "keep_verifier_repair"

  needs_instruction_change == true
    AND needs_verifier_change == false
    AND phase_signals.touched_relevant_files == false
    AND solver_signal != "weak"                                  → "keep_instruction_update"

Clean keep:
  all of (environment_readiness, dependency_completeness,
          verifier_integrity, instruction_verifier_alignment) >= 3  → "keep"

Downweight fallback:
  (vi + er + dc) / 3 >= 2.5 AND solver_signal != "weak"         → "downweight"

Otherwise                                                         → "reject"
```

## `keep_for_rl` derivation

```
keep / keep_verifier_repair / keep_instruction_update  → "keep"
downweight                                             → "downweight"
reject                                                 → "reject"
```

## Guidance

- A run can fail and still earn high `trajectory_progress_value`.
- Prefer evidence tied to the actual trajectory over generic advice.
- If multiple things went wrong, pick the dominant blocker for the primary dimension deduction and reflect the rest in additional struggle patterns.
- Use solver and oracle evidence separately before combining them.
- If the solver made little progress because of setup churn or bootstrap failures, treat oracle failure as weaker evidence.
- If the solver reached the likely fix area but the oracle still fails, treat oracle evidence as stronger and scrutinize verifier-task alignment.
- Distinguish: solver failure / environment failure / instruction-oracle mismatch / verifier weakness / insufficient signal due to time budget.
- Do NOT produce broad `recommended_actions` lists — use `verifier_diagnosis.repair_priority` and `instruction_tuning_advice` instead.
