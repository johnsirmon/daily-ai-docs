---
name: evidence-led-review
description: >
  Review this repository or compare model recommendations using measured artifacts
  and source-verified claims. Use for podcast-quality diagnosis, repository reviews,
  multi-model comparisons, and provider feasibility checks.
---

# Evidence-led review

## Establish evidence before asking models for opinions

1. Identify the actual entry point, branch, commit, workflow, and generated
   artifacts. Do not assume that legacy modules describe current production.
2. Read the relevant continuous code path directly. Delegate only substantial,
   independent work; do not split a small review into artificial specialties.
3. Measure the symptom: story selection, repeated event IDs versus repeated prose,
   recommendation mix, actual generation provenance, duration, and source coverage.
4. Distinguish observation, inference, recommendation, and unknowns. Cite public
   primary evidence and concrete file locations. Do not invent adoption metrics.

## Multi-model reviews

- Use additional models when requested or when there is a concrete independent
  objective. Honor explicitly requested models; otherwise retain agent defaults.
- First verify that each reviewer can access the assigned evidence. If filesystem
  access is absent, supply a bounded, non-sensitive evidence packet with exact
  code excerpts and artifact measurements. Label it an evidence-packet review,
  not an independent repository inspection.
- Require source/file references and a bounded stop condition.
- Adjudicate returned claims against the evidence. Retract unsupported findings
  explicitly; agreement between models is not verification.
- Reuse existing agents for follow-up instead of relaunching the same objective.

## Provider feasibility

- Separate consumer login, API credentials, billing eligibility, quota, model
  access, successful generation, and validated output. None implies the next.
- Verify current official documentation and actual account UI. Do not invent free
  quotas or assume consumer subscriptions include API credits.
- Distinguish provider availability errors from output/grounding errors. Do not
  edit prompts to cure HTTP 503. Use a bounded retry only when appropriate.
- Never relax a factual validator just to obtain a sample. Do not silently switch
  to a paid provider or change billing.
- When the user redirects the workflow, stop the superseded API attempts and
  update the plan rather than running both paths.

## Reporting

- State what was inspected and what was not: scripts are not listened-to audio;
  metadata is not full decode; decode is not semantic fact-checking.
- Preserve user-authored commits and unrelated changes.
- Maintain one current plan with concrete acceptance gates and blockers, rather
  than accumulating contradictory progress reports.
- Read actual current workflow files before documenting commands. Legacy skill
  examples and remembered workflow names are not authoritative.
- End with a verified outcome or a precise blocker, never a success-shaped proxy.
