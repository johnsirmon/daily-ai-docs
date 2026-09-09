# Daily AI Developer Brief

A concise, source-backed daily podcast for AI agent developers: what changed, why it matters, what is worth learning, and whether to act, watch, or skip.

## Podcast

Canonical feed after GitHub Pages deployment:

`https://johnsirmon.github.io/daily-ai-docs/podcast.xml`

On iPhone, open Apple Podcasts → Library → Follow a Show by URL, paste the feed URL, and follow it. The show then appears through Apple Podcasts in CarPlay; no custom CarPlay app is required.

## Today's signal

The daily workflow has not published its first manifest-driven edition yet. The retained feed contains the validated legacy archive; after deployment, this section is generated from the same episode manifest used for narration.

## Editorial contract

- One edition per day, including a short honest quiet-day edition when sources are healthy but nothing is actionable.
- Three to seven stories at most; tracked topics are not forced into every episode.
- Primary-source evidence is required for spoken factual updates.
- Each story ends with an `ACT`, `WATCH`, or `SKIP` recommendation.
- Routine patch noise, duplicate prereleases, lifetime-star lists, and unsupported adoption claims are excluded.
- A weekly YouTube pass can contribute at most one transcript-backed learning recommendation per edition. Video velocity is normalized by age and comparable channel performance; raw lifetime views do not count as a trend.
- YouTube is a discovery and learning signal, not a substitute for primary evidence about product changes. Relevant primary links found in video descriptions are retained in show notes.
- Collection, synthesis, TTS, upload, and feed failures leave the last good feed unchanged.

## Tracked areas

The curated sources in [`topics/topics.yaml`](topics/topics.yaml) cover GitHub Copilot, VS Code, OpenAI Codex, Claude Code, Gemini CLI, Hermes Agent, MCP, Agent Skills, agent evaluation, and observability. The daily publisher uses explicit public primary sources plus a bounded weekly YouTube learning digest.

## Source health

Source health is recorded per official repository/feed in every episode manifest. A source outage is reported separately from a healthy quiet day.

## Publication flow

`collect → validate → rank → manifest → narrate → TTS → decode/measure → upload immutable audio → verify HEAD/range → update RSS → deploy Pages → verify subscriber feed`

The versioned episode manifest is the source of truth. README and narration are rendered from it; README is never parsed back into podcast data.

See [operations and setup](docs/OPERATIONS.md) for secrets, commands, failure recovery, Apple Podcasts setup, and the CarPlay pilot checklist.

## Weekly YouTube signal

The Sunday workflow runs four focused searches through the YouTube Data API, fetches statistics in one batched pass, normalizes view velocity by video age and a channel/global baseline, and retrieves English transcripts only for the highest-ranked candidates. It stores five compact extractive takeaways in `data/youtube-trends.json`; full transcripts are never committed. The daily selector deduplicates these video IDs and caps them at one story so durable product updates remain the core of the show.
