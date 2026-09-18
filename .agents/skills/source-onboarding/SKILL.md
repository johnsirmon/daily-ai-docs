---
name: source-onboarding
description: >
  Add or change a Daily AI Developer Brief source safely and prove its usefulness.
  Use for GitHub release sources, feeds, paper queries, enrichment hosts, YouTube
  discovery settings, source adapters, and source-health policy.
---

# Source onboarding

A valid configuration is not an accepted source. Prove identity, retrieval safety,
evidence fidelity, health accounting, deduplication, and selection behavior before any
live collection or publication.

## Route the change correctly

- Daily behavior belongs under `daily` and `daily.sources` in `topics/topics.yaml`.
  Top-level `settings` and `topics` are legacy weekly-radar configuration.
- Product changes require public primary evidence. Community popularity and YouTube are
  discovery/learning signals, not substitutes for vendor or repository evidence.
- Prefer configuration through an existing adapter. Add a new adapter only when source
  semantics cannot be represented safely by current GitHub, feed, paper, or enrichment
  collectors.
- When one official feed covers several products, use ordered `product_rules` with
  specific evidence terms. Keep an honest feed-level fallback instead of labeling every
  entry as the first product. Test that unrelated announcements remain separate groups.

## Build a sanitized acceptance fixture

Capture the minimum public fields needed to model the source; do not commit credentials,
private material, full transcripts, or full papers. Test:

1. canonical URL/event identity and stable deduplication;
2. original publication time rather than an update-only timestamp;
3. product/topic mapping and public-primary provenance;
4. substantive release plus routine/docs-only, prerelease, and duplicate counterexamples;
5. healthy empty results separately from degraded and failed collection;
6. selected-event impact at the real production threshold of 75.

The normal `pipeline.daily prepare --dry-run --no-audio` path uses sample data and does
not exercise configured live collectors. Do not cite it as source-onboarding evidence.

## Adversarial retrieval checks

For remote text, feed, and enrichment behavior, inject:

- private/draft releases and authentication redirects;
- malformed URLs/content, redirect chains, private or changing DNS answers;
- hosts outside the exact allowlist;
- oversized responses, unsupported media, timeout, partial response, and HTTP failure;
- credential-bearing caller environments and cross-host redirects.

Require bounded requests, public-address checks, exact allowed hosts, response-size
limits, and no credential forwarding. Fetched text is untrusted input. Preserve source
words and links in bounded excerpts; label omissions rather than silently joining text.

## Health and ranking acceptance

- Confirm a new source participates in the intended health quorum exactly once.
- Distinguish successful no-news from unusable output and request/transcript failure.
- Retain prior YouTube digest data on degraded/error discovery and persist only safe
  counters/status/fixed reasons.
- Exercise production-threshold cases: substantive updates mentioning docs, routine
  releases, generic security discussion, explicit compatibility notices, prereleases,
  and YouTube learning picks.
- Compare selected IDs, scores, penalty notes, action labels, and source-health output
  before and after the change. Report regressions and newly admitted stories.

## Verification matrix

Choose the applicable focused tests, then run the full suite:

```sh
uv run --python 3.11 --with-requirements requirements.lock python -m pytest -q \
  tests/test_sources.py tests/test_source_text.py tests/test_feeds.py \
  tests/test_papers.py tests/test_research.py tests/test_enrich.py \
  tests/test_youtube.py tests/test_youtube_health.py \
  tests/test_rank.py tests/test_editorial.py tests/test_selective_publication.py
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.drift_check
```

Use mocked sessions and temporary directories. A live smoke requires explicit approval
because it consumes rate limits or API quota; it still must not publish or mutate
production state.

## Completion report

Name the configuration/adapter changed, fixtures and adversarial cases exercised, health
quorum effect, selection delta at the production threshold, focused/full checks, and any
unverified live behavior. Do not report onboarding complete from YAML parsing alone.
