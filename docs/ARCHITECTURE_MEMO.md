# Architecture Memo — Ship A (Single Agent)

## Decision
Ship **Architecture A, the single-agent baseline**. Do not ship the staged variant.

## Evidence
| Metric | Single (A) | Staged (B) |
|---|---:|---:|
| Correct recommendation | 100% | 100% |
| Approvals correct | 100% | 100% |
| Escalation correct | 100% | 100% |
| Policy compliant | 100% | 100% |
| Evidence grounded (programmatic) | 100% | 100% |
| Mean latency | 4.8 ms | 4.2 ms |
| p95 latency | 12.3 ms | 5.4 ms |
| Mean LLM calls | 0.0 | 0.0 |
| Mean tool calls | 5.0 | 5.0 |

Twelve cases, same set both sides, plus 6/6 public harness cases each. B never beats A on any quality metric.

## Trade-offs
B adds an Analyst plus Reviewer pass, a second prompt, and an evidence-pack handoff for zero measured gain: identical recommendations, approvals, flags, and grounding. Offline both are equally fast; with a live key B costs roughly twice the tokens and latency (two LLM calls vs one) and doubles the failure surfaceFake quote (malformed JSON, drift between passes) while the shared guard layer already enforces every safety outcome. A's single pass is easier to trace, test, and explain.

## Risks / limitations
No API key was configured, so numbers measure the deterministic core, not live LLM behaviour. Validate with a key: spot-check that the model respects code results, then re-run `python evals/run_eval.py`. The add-on overlap exception is keyword-based and narrow; review any new approve-with-overlap case. Hidden policies around seat capacity and renewals are unhandled by design and escalate.

## Why this is the right MVP
The client need is reliable triage with human control, not orchestration. A plus the guard layer delivers 100% escalation and grounding with one auditable pass, five traced tool calls, and a human queue. Simpler wins: ship A, spend the saved complexity on live-key validation and reviewer UX.
