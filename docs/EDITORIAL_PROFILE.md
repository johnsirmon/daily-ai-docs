# Engineering audience profile

`daily.editorial.audience_profile` in `topics/topics.yaml` is optional public
relevance context for the grounded daily brief. Remove it (or set it to null) to
retain the previous ranking and request payloads. It does not enable editorial
mode, add model calls, or alter publishing requirements.

The profile accepts exactly `experience` (`experienced` or `general`), `tools`,
and `priorities`. Lists accept only unique keys defined in
`pipeline/editorial_profile.py`: tools are vscode-insiders, copilot-chat,
copilot-cli, codex, hermes; priorities are agent-integrations, mcp, evals,
observability, handoffs, reliability, cost, wsl. No names, employer, family,
compensation, private projects, arbitrary prose, installed versions, or account
entitlements belong in this public configuration.

Selection first applies the existing novelty, substantive-evidence and developer
utility gates. Eligible events gain six ranking points for any tool match and
six for any priority match, at most twelve regardless of repeated keywords.
Matches use word boundaries in product, title and evidence, never source metadata.
This is a preference, not an evidence or security classifier. Existing source
priority and utility scores still matter; preferences do not guarantee coverage.
Research keeps its separate evidence and freshness requirements.

Drafting and the independent audit receive the same validated profile in a
separate request field. Both are instructed to use it only for relevance,
keep unknown version/build/plan applicability conditional, and explain an affected
workflow, why it matters, a bounded check, cost or caveat and what to ignore only
where evidence supports them. Unsupported slots are omitted rather than padded.
Source metadata cannot supply or override the profile. Existing quote, claim,
quantity, novelty, usefulness, two-call and duration gates remain authoritative.
Offline tests establish selection and request plumbing, not live model compliance.

The profile is transient request context, not source evidence. It is not added to
schema 1/2/3/4 manifests, evidence archives, narration metadata, audio, feeds,
release identities or recovery state. Existing stories and claim schemas remain
unchanged. There is no migration; removing the config is the rollback boundary.

Run offline checks with the locked development environment:

```sh
python -m pytest -q tests/test_editorial_profile.py tests/test_rank.py tests/test_editorial.py tests/test_grounded_editorial.py tests/test_daily.py tests/test_usefulness.py
python -m pytest -q
python -m pipeline.publish_check
python -m pipeline.drift_check
python -m compileall -q pipeline tests
git diff --check
```

This change does not repair provider availability or source discovery. Gemini
unavailability must still fail closed. The 36-hour collection window can lose
coverage after outages. Evals and observability lack dedicated primary collectors;
preferences cannot select undiscovered evidence. Notebook/browser integration is
outside this feature and requires a separate decision.
