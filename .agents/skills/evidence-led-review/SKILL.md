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

## Claim-level editorial acceptance

Use a claim worksheet for every consequential spoken or written claim:

| Claim | Event ID and primary URL | Exact support | Scope/quantity/eligibility/date | Verdict or correction |
|---|---|---|---|---|

- Inspect the primary HTML or visible page when simplified extraction may have
  omitted a qualification. Record the fallback used.
- Exact quote matching is necessary but not semantic entailment. Check that the
  source supports the asserted actor, action, population, timeframe, quantity,
  and recommendation.
- Require each number to be supported by the same claim's evidence. Do not borrow
  quantitative context from another claim or a release title.
- For research, retain method, evaluation setting, limitations, and
  author-reported/not-independently-reproduced status.
- Distinguish schema-2 independent model verification from schema-3 human/assistant
  transcript-to-source review. Never upgrade provenance labels to make an artifact
  eligible.
- Material errors require correction before publication. Preserve the exact
  correction and its provenance when the contract supports an audible prefix.

## Unpublished preview acceptance

1. Run mocked provider, schema, and preview tests before consuming quota.
2. Require explicit free-tier/quota authorization before live generation. Use a
   fresh output directory and current production history in a separate read-only
   checkout.
3. Evaluate story/event coverage, claim-local quantities, eligibility limits,
   research caveats, action labels, and script budget independently of style.
4. Validate actual audio bytes: checksum, full decode, measured duration, and media
   metadata. A duration label or successful generation is not audio acceptance.
5. Verify `data/`, `podcast.xml`, and `README.md` remain unchanged.
6. Classify provider availability, schema, grounding, audio, and delivery errors
   separately. Never add `[editorial-preview]` merely to rerun ordinary CI or weaken
   factual validators to obtain a sample.
7. Keep signed-in Notebook browser mechanics in `notebook-podcast`; do not duplicate
   them here.

## Instruction and workflow drift

For documentation, workflow, CLI, configuration, or agent-instruction changes:

- Inventory referenced commands, files, workflow names, triggers, permissions, and
  side effects; compare them with current code and `--help` output.
- Label each command offline, networked, quota-consuming, state-writing, or
  publishing. Do not let a safe-looking example conceal production effects.
- Run `tests/test_workflows.py`, `pipeline.publish_check`, and
  `pipeline.drift_check`; note that these checks do not prove complete semantic
  agreement among manifests, README, state, and receipts.
- Report stale legacy instructions separately from product defects and fix the
  authoritative source rather than copying corrected prose into several skills.

## Reporting

For audio-quality work, assess repetition, time to the first useful point, actionable takeaways,
pronunciation, pacing, joins, and source fidelity separately. Compare the same reviewed script when
auditioning voices. Record actual listening separately from ASR/metadata/automated measurements.
Do not claim that a pronunciation was heard incorrectly merely because ASR misspelled a product name.

- State what was inspected and what was not: scripts are not listened-to audio;
  metadata is not full decode; decode is not semantic fact-checking.
- Preserve user-authored commits and unrelated changes.
- Maintain one current plan with concrete acceptance gates and blockers, rather
  than accumulating contradictory progress reports.
- Read actual current workflow files before documenting commands. Legacy skill
  examples and remembered workflow names are not authoritative.
- End with a verified outcome or a precise blocker, never a success-shaped proxy.
