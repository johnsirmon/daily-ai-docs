# Daily AI Developer Brief: Editorial Improvement Brief

## Purpose and audience

Serve working developers who use AI tools but do not follow every product announcement.

Listeners should understand **what changed, why it matters, and how it could affect their work**.
The podcast should explain developments, not read release notes or production instructions aloud.

The reference is the explanatory depth of Gemini Notebook podcasts: connecting sources, explaining unfamiliar
concepts, and using concrete examples. This does not require two hosts, a particular voice provider, or imitation
of another show's wording. Better delivery alone will not fix weak analysis.

## Current feedback and implementation status

Listening feedback identifies these problems:

- Repeated product names, such as "Claude Code," make narration sound mechanical.
- Versions and low-level changes receive airtime without explaining their significance.
- Terms such as "Bedrock" appear without enough context for an unfamiliar listener.
- Phrases such as "read the primary source and assess" sound like production instructions, not finished analysis.
- Stories lack the broader context needed to judge usefulness or understand what is genuinely new.

These are listener observations, not a completed technical diagnosis or a claim that every episode has these problems.
Some research and quiet-day functionality may already exist. Its implementation and effectiveness are unverified
in this brief; check existing behavior before proposing new components.

This document defines desired outcomes. It does not change pipeline behavior, publication policy,
or historical episodes. Section 9 maps the brief to the current implementation and plans dependency-free
improvements; those changes are not yet implemented.

## 1. Explain the change and its consequences

For each main story, answer:

1. **What changed?** Describe the meaningful difference from the previous behavior or existing approach.
2. **What context is needed?** Briefly explain the product, concept, or workflow a listener needs to understand.
3. **Why does it matter?** Identify who benefits, who is unaffected, and any material limitations.
4. **What does it look like in practice?** Give a concrete developer scenario when it helps explain the impact.
5. **What is established versus inferred?** Separate documented behavior, reported results,
   and editorial interpretation.

Use official documentation and relevant earlier announcements alongside the day's primary source.
Use reputable independent analysis and comparisons when they add context, naming where they come from.
Label older material as background rather than presenting it as a new development.

Do not pad every story with the same spoken headings or a ritual "what this means for developers" sentence.
These questions are an editorial checklist, not a script to read aloud.

## 2. Prioritize usefulness and resist bias

Use open-source repository trends and other trackable AI developer signals to discover stories.
Then prioritize demonstrated usefulness and the strength of the evidence, regardless of vendor or popularity.

Potential discovery signals include:

- Repository growth over a stated period, rather than lifetime stars alone.
- Contributor participation, release activity, and meaningful changes in issue or discussion activity.
- Package-download trends where comparable historical data is available.
- Observable downstream dependencies and documented integrations, with coverage gaps acknowledged.
- Public developer discussions, reproducible evaluations, and documented workflow experience.

Treat these as indicators to investigate, not proof of quality, adoption, or broad developer consensus.
Downloads can include automated activity; discussion volume can reflect promotion or problems rather than value.
Record the source, observation window, and comparison baseline for any narrated trend claim.
If comparable measurements are unavailable, do not describe a project as accelerating or gaining adoption.

Assess attention, practical use, and maintainability separately. A surge in interest does not establish that a tool
works well or will remain supported. Consider contributor concentration, governance, and licensing when those factors
materially affect a developer's decision. Compare similar project types over consistent periods, and distinguish a
one-off launch spike from sustained activity when historical data permits.

"Unbiased" is a goal supported by explicit practices, not a guarantee:

- Apply the same evidence and usefulness standards to commercial products and open-source projects.
- Attribute vendor claims and independent opinions; identify relevant affiliations or sponsorship when known.
- Explain tradeoffs and contrary evidence instead of reproducing promotional framing.
- Do not treat attention as merit, obscurity as weakness, or open source as an automatic recommendation.
- Distinguish genuinely independent evidence from articles repeating the same original claim.

## 3. Filter technical detail and make narration natural

Include patch versions, small fixes, or warnings only when they materially affect workflows, reliability,
security, cost, or compatibility. Explain that effect rather than reading the changelog entry.
Speak an exact version when listeners need it to identify an affected release, migration, or required fix.
Keep other identifiers and supporting details in written notes when useful.

For narration:

- Introduce a product clearly, then use natural references without repeating its name in adjacent sentences.
- Explain unfamiliar terms at their first relevant use; avoid both unexplained jargon and repeated definitions.
- Group closely related changes into one explanation rather than several near-identical announcements.
- Use transitions that explain connections, not formulaic introductions for every item.
- Remove drafting prompts, verification instructions, evidence IDs, and internal process language from spoken text.
- Give the actual analysis instead of repeatedly telling listeners to "read the source and assess."

Practical listener advice is still welcome when specific and supported. "Check whether your workflow depends on
the old default" can be useful; a generic instruction to perform the missing research is not a substitute for analysis.

## 4. Use quieter days for useful research and critical comparisons

When few news developments meet the usefulness bar, look for recent whitepapers and research papers with
practical relevance. Quiet-day coverage should not simply repeat marginal release notes or manufacture urgency.

For a paper considered for coverage:

1. Review the full text, not just its title, abstract, or a promotional summary.
2. Explain the problem, method, claimed contribution, and reported result in accessible language.
3. Compare it with relevant existing methods, tools, and prior work.
4. Assess applicability: likely users, integration effort, compute or data requirements, and practical constraints.
5. Identify limitations, benchmark conditions, and gaps between the experiment and real developer workflows.
6. Distinguish author-reported findings from independent validation; never imply reproduction without testing.
7. Offer a proportionate conclusion: worth investigating, useful in a specific setting, incremental, or unproven.

Independent reproduction is not a prerequisite for discussing a paper, but its absence must constrain the conclusion.
If full text or sufficient supporting evidence is unavailable, do not present a substantive paper review as completed.

Also consider high-attention subjects whose practical novelty may be limited. Ask:

- What existing capability does this duplicate, and what evidence supports that comparison?
- Is there a meaningful improvement in usability, reliability, cost, access, integration, or performance?
- Does a comparison use equivalent tasks, conditions, and baselines?
- Is the contribution genuinely new, a useful repackaging, or mainly a new label for an established approach?

Do not call something redundant or overhyped merely because a similar tool exists.
Packaging and accessibility can be useful contributions even without a new underlying technique.
Critique specific claims and tradeoffs, not the people or organizations behind them.
Attention alone does not justify a recurring "hype" segment.

If neither news nor research supports a useful episode, do not add filler or lower the evidence bar.
Verify the repository's existing shorter-episode or editorial-skip behavior before changing that policy.
Source outages and failed research must not be presented as healthy quiet-news days.

## 5. Research before writing the story brief

Use public primary sources for factual product and research claims.
Independent commentary can support comparisons and interpretation but must be attributed and assessed critically.
Keep source links and claim support in written notes and the existing evidence workflow, not as spoken process clutter.

Use the available Exa MCP search and page-fetch tools during operator-assisted research to improve the actual briefs,
not merely to collect more links. Another suitable available search tool can serve the same purpose.
This does not imply that the automated publishing pipeline already uses that integration.

For each promising story:

1. Find the primary announcement or paper and read the relevant underlying material.
2. Search official documentation and earlier releases for what was already possible.
3. Look for existing alternatives and independent analysis, including evidence that challenges the headline claim.
4. Compare the proposed benefit with a realistic developer workflow and the simpler existing solution.
5. Draft a source-backed explanation; do not present unresolved questions or unsupported implications as facts.

The resulting editorial brief should contain:

- The development and why it deserves attention now.
- What a developer could already do, and the actual difference this introduces.
- The affected workflow, a concrete example, and situations where the change is not relevant.
- Evidence supporting the benefit, contrary evidence, limitations, and the confidence warranted by those sources.
- A practical conclusion, including "no reason to switch yet" when that is the supported assessment.
- Source URLs, dates, claim support, and attribution for independent commentary.

These are logical editorial requirements, not a demand for new persisted schema fields.
Reuse the existing research and evidence structures where they already support this work.

Research safeguards:

- Prefer an existing suitable integration over adding another dependency.
- Do not assume a tool is free or unlimited merely because it is available; respect configured access and usage limits.
- Treat search results and generated search summaries as discovery aids, not verified evidence.
- Open and review the underlying sources before relying on their claims.
- Use only public research queries; do not send private repository content or credentials to external services.
- Report unavailable or insufficient evidence explicitly rather than inventing context or implying research succeeded.

Research should improve the explanation and the decision to cover a story, not just increase the citation count.

## 6. Narration examples

The following examples are illustrative, not reports about actual releases, papers, or measured results.
Any comparable claim in a real episode must be verified against its sources.

### Replace changelog repetition with a workflow explanation

**Avoid:**

> Tool X version 1.2.3 adds approval handling. Tool X also updates permissions. Tool X fixes an approval issue.

**Prefer:**

> This update changes how the coding assistant asks permission before running a command. If you use it to work
> across several repositories, the practical question is whether approval stays limited to the task you intended.
> The documented change concerns that approval boundary; it does not establish that the assistant writes better code.

The improved version explains the workflow and limits the conclusion instead of inflating a small change.

### Explain unfamiliar terms and condition the relevance

**Avoid:**

> Bedrock support changed. The release also warns on build fallback.

**Prefer:**

> Amazon Bedrock is AWS's managed service for accessing AI models. This change matters if your coding tools connect
> through that service. If your tools connect directly to a model provider instead, this part of the update does
> not change that workflow.

Omit the build-fallback warning unless its source establishes a meaningful effect on developer work.
If it does, explain that effect rather than merely repeating the warning.

### Provide analysis instead of leaking instructions

**Avoid:**

> Read the primary source and assess applicability. Include an explicit reasoning summary.

**Prefer:**

> The authors report an improvement on their benchmark, but the evaluation does not cover the larger repositories
> that would matter to many teams. This is a reason to investigate the method, not yet a reason to replace your
> current workflow.

### Critique limited novelty without dismissing useful engineering

**Avoid:**

> Everyone is talking about this, but it is just reinventing the wheel.

**Prefer:**

> The core technique already exists in earlier tools. The contribution here is a simpler integration, rather than
> a new capability. That could still help a team struggling with setup, but it is not evidence of better model quality.

## 7. Acceptance criteria

Use these criteria to review the selected stories, final narration, supporting notes, and resulting audio.

### Story selection and grounding

- [ ] Every main story identifies a meaningful change or research contribution and its developer relevance.
- [ ] Every narrated factual claim has traceable source support; quantities have support for the exact quantity claimed.
- [ ] Every narrated trend identifies its source, observation period, and baseline in the supporting notes.
- [ ] No claim of adoption or quality rests only on stars, downloads, release volume, or discussion volume.
- [ ] Independent analysis is attributed, and opinion is distinguishable from documented fact.
- [ ] Each main story's brief compares the new development with prior capability or a relevant existing alternative.
- [ ] Research considers contrary evidence; if none is found, the brief does not treat that as proof of the claim.
- [ ] Previously covered developments return only with a new contribution or clearly labeled, necessary context.

### Explanatory depth and natural delivery

- [ ] Each main story explains what changed, why it matters, who is affected, and material limitations.
- [ ] Main stories include a concrete workflow example where applicability would otherwise remain abstract.
- [ ] Unfamiliar terms are explained before listeners need them to follow the argument.
- [ ] Every spoken version number or low-level fix is necessary to understand a material impact or take an action.
- [ ] Related updates are grouped; adjacent sentences do not repeat a product name without a clarity-related reason.
- [ ] Narration contains zero producer directives, drafting prompts, evidence IDs, or verification instructions.
- [ ] Context and examples do not introduce capabilities, causal effects, or performance claims unsupported by evidence.

### Research and novelty assessment

- [ ] Quiet-day selection considers relevant recent papers when suitable news is insufficient.
- [ ] Every covered paper has a full-text review addressing method, result, applicability, prior work, and limitations.
- [ ] Author-reported results and independently validated findings are explicitly distinguished.
- [ ] Every claim of limited novelty identifies a concrete existing approach and a source-backed comparison.
- [ ] Useful integration or accessibility improvements are considered before dismissing something as redundant.
- [ ] Missing evidence results in a qualified conclusion or omission, not a confident recommendation or takedown.

### End-to-end review

- [ ] Evaluate a representative news-rich episode and a thin-news case against this checklist.
- [ ] Include at least one jargon-heavy story and one paper or limited-novelty comparison in the review sample.
- [ ] Compare old and revised narration using the same source material to isolate improvements in explanation.
- [ ] After listening, a reviewer can explain the change, affected workflow, and main limitation without reading notes.
- [ ] Review audio and transcript; document repetition, unexplained terms, and instruction leaks.
- [ ] Record who listened and which portions were reviewed; do not imply a listening review occurred when it did not.
- [ ] Record pass/fail evidence and remaining gaps; a prompt change or automated test alone does not prove quality.

## 8. Implementation review before changes

Map these requirements to existing selection, research, drafting, verification, narration, and review behavior.
Classify each as already effective, present but ineffective, missing, or unverified.
In particular, inspect the existing quiet-day research path before proposing a replacement.

Preserve the manifest as the source of truth, traceable claims, publication safeguards, and historical episode identity.
Do not loosen evidence checks to obtain more conversational narration.
Later schema, provider, ranking, or publication-policy changes need their own scoped implementation and validation.

## 9. Dependency-free implementation plan

### Scope and non-goals

Extend the manifest-driven daily pipeline, not the legacy README-to-podcast path.
Keep [requirements.txt](requirements.txt) and [requirements.lock](requirements.lock) unchanged.
Use the existing Python standard library, installed packages, pytest fixtures, source adapters, model client,
and audio tools. Do not add an NLP package, crawler, vector store, database, service, or model/provider.
Existing dependencies still need to be available in the execution environment; no new ones are required.

Keep these boundaries throughout implementation:

- No automatic activation of grounded editorial mode, new credentials, extra model calls, or increased quotas.
  Dependency-free does not mean network-free or cost-free.
- No new required manifest fields or replacement editorial framework. Prefer the existing story fields,
  `editorial.spoken_text`, `editorial.claims`, and `paper_review`.
- No post-verification prose rewriting. Changes to generated speech happen before independent verification.
- No weakening of claim-local quantity checks, full-text requirements, source-health checks, or media validation.
- No edits to historical episodes, release media, GUIDs, publication receipts, state, or generated output.
- No automatic research-only episode or shorter grounded-episode policy. Those require separate approval.

### Inspected baseline and gaps

This mapping is based on source and test inspection at commit `7045cfe`, not a listening review.
Deployed repository-variable overrides, live source availability, and current episode quality were not audited.
"Already effective" below means an explicit implementation safeguard with regression coverage, not proven
listener satisfaction. Behavioral changes still require rerunning the relevant tests.

| Requirement | Classification | Existing behavior and gap |
| --- | --- | --- |
| Change and relevance | Present but ineffective in fallback | Generic relevance/advice is emitted verbatim. |
| Grounded explanatory writing | Present; effectiveness unverified | Drafting and verification already request impact. |
| Earlier capability and comparisons | Missing end-to-end | Article completion is not comparative research. |
| Grouping and noise filtering | Present; effectiveness unverified | Grounded grouping exists; default mode differs. |
| Natural references and jargon | Missing targeted checks | Passage duplication checks do not assess explanation. |
| Claims and quantities | Already effective structural safeguards | Semantic entailment still needs verification. |
| Attention versus adoption | Present, partial; unverified | Star deltas exist; wider comparable signals do not. |
| Full-text paper review | Present; effectiveness unverified | Collection and structured review already exist. |
| Research-only quiet-day coverage | Missing by explicit policy | Papers supplement product stories, not replace them. |
| Healthy skips versus failures | Already effective safeguard | Failed coverage/provider stages cannot become success. |
| Same-source listening comparison | Unverified for this brief | No before/after listening evidence collected here. |

Concrete implementation anchors:

- [daily.py](pipeline/daily.py) selects deterministic or grounded processing.
  [topics.yaml](topics/topics.yaml) disables grounded editorial by default; the
  [daily publisher](.github/workflows/update-radar.yml) also defaults `AI_EDITORIAL` to `off`.
  `AI_SYNTHESIS` only reorders/relabels deterministic stories; it does not write richer explanations.
- [rank.py](pipeline/rank.py), `event_to_story`, supplies the exact generic "Read the primary source and assess"
  rationale. [narrate.py](pipeline/narrate.py), `manifest_to_narration`, speaks it in schema 1.
  Changing only the grounded prompt would leave this path unchanged.
- [synthesis.py](pipeline/synthesis.py) already drafts and separately verifies schema-2 prose in two requests.
  [schema.py](pipeline/schema.py) already checks evidence IDs, exact quotations, quantities, research limitations,
  and repeated sentences. Its primary-only contract does not admit independent commentary as equivalent evidence.
- [detail.py](pipeline/sources/detail.py) completes short or excerpted articles through bounded, allowlisted fetches.
  It does not retrieve prior capability or alternatives just because a story lacks context.
- [papers.py](pipeline/sources/papers.py) collects recent, unreviewed arXiv HTML full text.
  [text.py](pipeline/sources/text.py) rejects missing or oversized full text rather than silently truncating it.
  Selection permits one paper only alongside product news; preparation also rejects research-only output.
- [audio_quality.py](pipeline/audio_quality.py) detects adjacent repeated passages of at least 12 words,
  not repeated product names in otherwise different sentences. Its preparation check is opt-in.
- [evidence_archive.py](pipeline/evidence_archive.py) already retains bounded claim excerpts and provenance hashes.
  [preview.py](pipeline/preview.py) already isolates preparation from publication and exports review artifacts.
  Neither needs a replacement subsystem.

### Phase 1: Establish a reproducible editorial baseline

**Extend:** [editorial fixtures](tests/fixtures/editorial.json),
[grounded tests](tests/test_grounded_editorial.py), and
[selective-publication tests](tests/test_selective_publication.py).

1. Add small synthetic or bounded public-source cases for news-rich coverage, thin news with a suitable paper,
   paper-only candidates, a source outage, a jargon-heavy change, and a limited-novelty integration.
2. Include repeated product names, routine patch churn, a material security fix requiring an exact version,
   unsupported benefit claims, and the producer-directive examples from this brief.
3. Freeze the event content, timestamps, confirmed history, configuration, and mocked model outputs.
   Compare old and revised behavior against the same inputs in both schema-1 and schema-2 paths.
4. Record per-story pass/fail against section 7. Separate automated findings from semantic review and actual listening.
   Use existing test helpers and preview artifacts, not a new evaluation framework.

**Acceptance:** Every failure has a reproducible case and expected outcome. Tests use no live provider,
search, TTS, or source calls. The baseline records which feedback is reproduced and which remains unverified;
do not claim every historical episode has the reported defects.

### Phase 2: Improve the existing spoken paths

**Implemented, 2026-09-19 (bounded text-contract scope):** Fresh schema-1 preparation opts into
`generation.narration_style: explanatory-v1`; historical unmarked rendering and candidate recovery remain unchanged.
The marked path removes generated relevance/advice, duplicate lead announcements, spoken action labels, and written
excerpt notices. It retains complete bounded source evidence so late versions and conditions survive, with explicit
prerelease/learning qualifications and fail-closed word/character budgets. It does not fabricate explanatory context,
strip versions globally, or substitute product names with pronouns.
Fresh marked scripts are checked before TTS against the intersection of existing edition and narration-plausibility
duration gates. Insufficient material uses the existing healthy-skip receipt without padding or relaxing minima.
Measured media validation remains mandatory for viable scripts; provider failures remain failures.

Schema-2 drafting and independent verification now jointly require supported before/after context, necessary jargon
definitions, concrete supported workflows, limitations, unambiguous references, and necessity-only version speech.
Known producer directives are rejected before verification across newly authored prose, not source quotes or historical
manifests. Verified schema-2 narration and imported schema-3/4 transcripts are not rewritten. Focused fixtures cover
legacy byte equality, marked round-trip/preparation, unchanged candidate recovery, conditions/versions, instruction
rejection, legitimate listener advice, and paper question/result rendering. No listening improvement is claimed.

**Extend:** [rank.py](pipeline/rank.py), [narrate.py](pipeline/narrate.py),
[synthesis.py](pipeline/synthesis.py), and existing spoken-text validation.

1. In deterministic narration, remove generic relevance filler, producer-like advice, repetitive lead announcements,
   and spoken action-label recitation. Keep source-backed change wording, applicability warnings, and written
   recommendations. Do not fabricate explanatory context to make deterministic output sound researched.
2. Strengthen the existing draft and verifier instructions together: explain the before/after difference, define
   necessary unfamiliar terms, identify affected and unaffected workflows, and retain material limitations.
   Use a concrete hypothetical workflow only when its factual premises are supported; label it as an example.
3. Keep full product identification at first use. Request natural later references only where the referent is clear.
   Keep exact versions when needed for a fix, migration, or compatibility boundary; leave other identifiers in notes.
4. Add targeted checks for known producer directives, including "Include an explicit reasoning summary."
   Reject new grounded drafts containing those directives rather than silently deleting already verified text.
   Preserve legitimate listener advice such as checking dependence on a documented old default.
5. Reuse the existing repetition helper for diagnostics. Treat adjacent product-name repetition and unexplained
   terminology as review findings, not blanket regex bans. Do not build a new NLP detector or automatic synonymizer.

**Acceptance:** Fixture narration has zero producer directives, retains every necessary version/condition,
and does not add unsupported capabilities or quantities. Grounded explanations pass the existing independent
verification step within the same two-call budget. No verified or imported transcript is rewritten afterward.
Deterministic output improves in clarity without claiming the analytical depth of grounded mode.

**Tests:** Extend [test_narrate.py](tests/test_narrate.py), [test_editorial.py](tests/test_editorial.py),
[test_grounded_editorial.py](tests/test_grounded_editorial.py), and [test_schema.py](tests/test_schema.py).
Test positive listener advice as well as negative instruction leaks. Keep stricter new-draft checks from
retroactively invalidating immutable historical manifests.

### Phase 3: Improve evidence use before adding discovery

**Implemented subset:** Existing `paper_review.question` and `paper_review.result` are exposed in daily show notes
and rendered briefs; presentation guidance now treats schema 2 and marked schema 1 as non-label-reciting narration.
**Deferred:** Prior-capability source collection, adapter enrichment changes, automated background/secondary-source
contracts, and live audio evaluation. Prompt improvements use only evidence already supplied and do not establish
that additional research was performed. No new dependency, provider/quota activation, research-only daily edition,
or weakened evidence/media gate is part of this change.

**Extend:** Existing article enrichment, evidence payloads, claim review, and written notes.

1. First use context already present in the collected primary evidence. Require the draft to explain supported
   prior behavior and tradeoffs rather than repeat release-note fragments. If evidence does not establish a
   comparison, qualify or omit it; history remains a novelty check, not a factual source.
2. For sources whose existing enrichment loses necessary context, improve article extraction or bounded
   detail retention through the current adapter. Retain the actual detail URL and provenance, request/byte limits,
   host allowlists, explicit failure diagnostics, and publication excerpt limits.
   A URL in `corroboration_urls` alone is not proof that its contents were fetched or support a claim.
3. During operator-assisted review, use already available search/page-fetch tools to investigate prior capability,
   alternatives, affiliations, and contrary evidence. Record source dates and distinguish older background from news.
   Do not add Exa or another search SDK, CI secret, or mandatory automated search stage.
4. Keep independent commentary attributed in the operator's review material. Do not relabel it as primary,
   concatenate unrelated pages into an unattributed event, or bypass the primary-only schema-2 verifier.
   Automated use of cross-source background or secondary opinions needs the separately scoped contract below.
5. Update [daily show notes](pipeline/daily.py) and [README rendering](pipeline/render.py) together to expose
   existing supported context, conclusions, research results, and limitations without internal instructions.
   Correct mode-specific presentation text: schema-2 narration is conversational, not required to recite action labels.

**Acceptance:** Every added spoken fact remains traceable through the existing claim/event/quote relationship.
Archiving preserves enough exact support to validate the manifest after full text is removed.
Missing context is visible in review findings, not disguised as completed research.
Historical serialization and recovery continue to work without new required fields.

**Tests:** Extend [source-text tests](tests/test_source_text.py), [grounded tests](tests/test_grounded_editorial.py),
[archive tests](tests/test_evidence_archive.py), [render tests](tests/test_render.py),
and [recovery tests](tests/test_recovery.py). Include missing context, misleading comparisons,
enrichment failure, and archive round trips.

### Phase 4: Refine usefulness and research within current policy

**Extend:** [rank.py](pipeline/rank.py), [daily.py](pipeline/daily.py), and the existing paper-review prompts.

1. Tune selection only against demonstrated fixture failures. Preserve substantive-evidence gating before scoring,
   same-product limits, stable/prerelease distinctions, and evidence-based novelty checks.
   Do not suppress a material fix merely because its version looks like a patch.
2. Add vendor-neutral counterfactual tests: equivalent evidence, priority, dates, and measured signals must receive
   equivalent eligibility and scoring regardless of product name. Audit configured priorities separately;
   do not silently change weights, tracked sources, or product budgets under a narration fix.
3. Keep measured star momentum as a bounded discovery signal, never a claim of adoption or quality.
   Confirm valid observation dates and comparable baselines; do not infer acceleration from a single delta.
   Current model evidence payloads omit momentum metadata, so do not instruct models to narrate those trends.
   Leave them unspoken until source, window, baseline, and claim-level support can all be retained.
4. Improve existing `paper_review` content: method and evaluation setting, author-reported result, prior-work
   comparison when supported by the supplied paper, practical requirements, limitations, and proportionate takeaway.
   A paper's account of prior work remains author-reported, not an independent comparison.
5. Exercise thin product-news plus research, paper-only, insufficient full text, repeated papers, oversized papers,
   and research-service failure. Retain the 30-day first-publication window and one-paper limit.
   Healthy no-news still skips; source/provider failure must remain distinguishable from that outcome.

**Acceptance:** Routine churn cannot outrank meaningful changes solely through attention signals.
Valid security/compatibility fixes remain eligible. Research narration retains its exact reviewed limitations,
author-reported/not-reproduced disclosure, and existing useful-word and measured-duration budgets.
No research-only episode, filler, or automatic reduction of minimum episode length is introduced.

**Tests:** Extend [test_rank.py](tests/test_rank.py), [test_papers.py](tests/test_papers.py),
[test_selective_publication.py](tests/test_selective_publication.py), and
[test_grounded_editorial.py](tests/test_grounded_editorial.py).

### Phase 5: Verify quality and roll out without publication changes

Implement phases in order, using small changesets with their regression tests. Then:

1. Run the directly affected tests, followed by the full existing suite before committing.
   Use the already provisioned Python 3.11 environment with locked dependencies; do not introduce test tooling.
2. Run the offline operating contracts in [test_skills.py](tests/test_skills.py) and
   [test_workflows.py](tests/test_workflows.py), plus `pipeline.publish_check` and `pipeline.drift_check`.
   These inspect contracts/artifacts; they do not prove semantic quality or subscriber delivery.
3. Review old/revised scripts using the same evidence and confirmed history.
   Reuse test stubs for repeatable comparisons; a live preview recollects news and is not itself a controlled A/B test.
4. Only after explicit authorization for existing provider access/quota, use the existing unpublished preview flow.
   It is networked, may consume quota, and writes a fresh preview directory; it must not publish.
   Keep current production history read-only and verify that data, README, and feed files remain unchanged.
5. For each review case, record instruction-leak count, repeated-name findings, unexplained-term findings,
   unnecessary-version findings, unsupported-claim count, and pass/fail for every explanatory criterion in section 7.
   Passing requires zero instruction leaks and unsupported claims, and resolution of every material review finding.
6. Listen to the complete representative news-rich sample and a thin-news sample that legitimately qualifies.
   If thin news correctly skips, record that result and use the mocked thin-news script for textual checks instead.
   Record listener identity, audio checksum, portions reviewed, and remaining gaps.
   The listener must explain each main story's change, affected workflow, and principal limitation without notes.
7. Update the directly affected [operations guide](docs/OPERATIONS.md) and generated presentation contracts
   alongside implementation. Keep deployment flags unchanged until the owner accepts the preview.
   Roll back code/configuration for future preparation if needed; never replace already published media.

No implementation validation in this plan requires dispatching a publisher, calling `finalize` or `confirm`,
or performing live collection, model generation, ASR, or TTS during ordinary tests.
Actual audio acceptance is a separate authorized step and cannot be replaced by passing mocked tests.

### Explicitly deferred decisions

These remain visible gaps, not implied deliverables of the compatible changes above:

- **Research-only quiet days:** Requires an approved publication-policy change across selection, preparation,
  skip/health behavior, budgets, rendering, and tests. Extend the current paper path if approved; do not create
  a second research pipeline.
- **Automated background and independent comparisons:** Requires a scoped evidence/provenance contract for
  dated background and attributed secondary interpretation. Define claim-to-source linkage and archive behavior
  before expanding ingestion. Never weaken primary-source requirements just to satisfy a prompt.
- **Broader trend metrics:** Contributor, download, dependency, governance, and discussion trends need comparable
  history and coverage assessment. Do not add collectors or narrate adoption until that evidence exists.
- **Provider or duration changes:** New voices, services, credentials, model calls, and shorter grounded editions
  are unnecessary for the initial improvements and outside this plan's compatible rollout.

## Research informing this brief

The following public sources were found through Exa and their relevant page text reviewed on September 19, 2026:

- [CHAOSS: Project Popularity](https://www.chaoss.community/kb/metric-project-popularity/) identifies multiple
  engagement signals, including downstream dependencies, and recommends filtering by time period, platform, and
  project type. This informs the use of comparable, multi-signal trend evidence.
- [CHAOSS: Assessing Viability](https://www.chaoss.community/practitioner-guide-viability/) treats project viability
  as broader than popularity, including governance, community, and strategy. This informs the separation of
  attention from maintenance and adoption risks.
- [NeurIPS Paper Checklist](https://neurips.cc/public/guides/PaperChecklist) asks whether claims match demonstrated
  results and scope, whether limitations are acknowledged, and whether results can be reproduced or verified.
  This informs the research-review requirements without treating missing code as automatic proof of weak research.

These sources inform the evaluation method; they do not establish that any specific AI tool or paper is useful,
redundant, or independently validated. The editorial priorities and acceptance criteria above are this project's
requirements, not policies attributed to CHAOSS or NeurIPS.