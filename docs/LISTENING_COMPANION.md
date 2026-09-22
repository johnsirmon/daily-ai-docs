# Offline listening companion

`pipeline.listening_site` builds a local, static listening companion without network access, model calls, audio
generation, publication, or changes to podcast history. It is an unpublished preview tool, not a GitHub Pages
integration.
Workflow integration is deferred because publishing workflows and production approval are reserved scopes.

## Accepted inputs

The generator reads only:

- an explicit RSS file;
- an explicit directory of accepted episode manifests;
- an optional reviewed `data/podcast-metadata.json`-shaped catalog;
- the listening-site stylesheet; and
- optional local feed and artwork files copied byte-for-byte into the preview.

It never parses `README.md`, delivery receipts, generation caches, request blobs, full transcripts, or full research
papers. It does not fetch artwork or audio. RSS is the episode allowlist; a manifest that is not represented in RSS
receives no page.
A missing receipt is not an error because this preview does not create or replace publication state.
The RSS bytes are captured once. Parsing, an optional byte-for-byte copy, and the reported SHA-256 use that same
snapshot even if another process later changes the source file.

For a manifest-backed episode, the manifest must have `candidate` or `published` status and must match the RSS GUID,
publication timestamp, enclosure URL, byte length, media type, and duration. A candidate is labeled
"Candidate — not confirmed" and is never presented as confirmed. An RSS-listed draft receives no page. Historical RSS
items without manifests retain reviewed catalog or feed copy and links under an explicit limited-record label; the tool
does not reconstruct claims from current documentation.
`--copy-feed` fails closed if any RSS-listed draft is withheld, rather than exporting draft text or media in a copied
feed.

## Build a preview

Use a new output path outside the input locations. Existing outputs are never replaced. Inputs and the output parent
must not be symlinks. After validation, the generator atomically reserves the output directory with exclusive creation;
it never renames over a competing directory. The reserved directory remains mode `0700` while a hidden child is built,
so complete-site visibility is not claimed to be atomic. Success moves the validated children into place and changes the
directory to mode `0755`. Failure removes the reserved directory only when its device/inode identity still matches the
generator's reservation; a competing path is left untouched.

```bash
python -m pipeline.listening_site \
  --feed podcast.xml \
  --manifests data/episodes \
  --metadata data/podcast-metadata.json \
  --stylesheet assets/listening-site.css \
  --artwork assets/podcast-cover-v4.jpg \
  --copy-feed \
  --output /absolute/new/path/listening-companion
```

Open `/absolute/new/path/listening-companion/index.html` directly in a browser. The generated site uses stable
SHA-256-derived filenames rather than episode IDs as paths. It has no JavaScript, autoplay, tracking, search index, or
embedded raw HTML. Audio controls use `preload="none"` and link to the existing RSS enclosure; the generator creates no
media.

If `--copy-feed` or `--artwork` is supplied, the copied bytes are unchanged. The stylesheet is likewise copied
unchanged. The preview's Content Security Policy blocks scripts, connections, forms, objects, frames, and inline
executable content.
All text is HTML-escaped. Every rendered link must be an ASCII, credential-free public HTTP(S) URL with a strict DNS
name or canonical global IP address. Controls, whitespace, backslashes, encoded authorities, hexadecimal numeric labels
(including bare `0x` prefixes), ambiguous numeric hosts, private IPs, and nonstandard ports are rejected without
changing accepted URL bytes. Validation is syntax- and IP-literal-based: it makes no DNS request and does not claim that
a DNS name cannot later resolve to a private address.
RSS is deliberately UTF-8-only; other encodings, DTDs, and entity declarations are rejected before XML parsing.

## Listener-facing content

The index lists the reviewed or RSS title, actual RSS `published_at` value, daily/special/archive label, acceptance
label, and duration. Complete accepted descriptions remain available in collapsed native `details` elements instead of
expanding every card. The index and episode pages label the canonical existing public RSS feed for subscription without
implying that the offline preview is deployed. Detailed pages expose only accepted manifest fields:

- accepted change, why it matters, unchanged ACT/WATCH/SKIP action, and rationale;
- cited source links without upgrading their authority;
- research question or experiment, method, author-reported result, limitations, takeaway, and evidence status;
- a recorded correction before any recommendations;
- coverage gaps, exclusions, and accepted show notes;
- compact source-health counts that distinguish healthy no-news, healthy updates, degraded, and error states without
  exposing source names, raw errors, or private paths; and
- the schema-specific AI narration disclosure.

Narration/transcript bodies, raw review claims, private paths, caches, and provider payloads are intentionally excluded.
Schema 1 is described as source-based AI narration, schema 2 as independently evidence-checked, and schemas 3/4 as
transcript-and-source reviewed. Those disclosures do not imply human listening or live delivery.

## Verification boundary

Automated tests cover XSS escaping, browser-ambiguous URLs, UTF-16/entity input, traversal-safe filenames, symlink and
output-overlap rejection, exclusive output reservation, coherent feed snapshots, manifest/feed media mismatches, draft
copy refusal, candidates, missing receipts, legacy records, deterministic output, unchanged input hashes, source-health
projection, and isolated schema 1/2/3/4 semantic records. Synthetic rollover coverage proves that a subsequent valid
publication does not invalidate fixed semantic assertions. The current-repository smoke derives its episode invariants
from current inputs instead of fixing mutable history counts.

A historical preview may still be measured separately against an explicitly reported commit and input hashes. At the
pinned baseline used for this change, manual artifact checks cover:

- `daily-2026-09-18-notebook-cde95bbf`, including the member-versus-organization correction and SWE-bench limitations;
- `adhoc-2026-09-21-e8e033d99b413fcd1c65cea0`, retaining actual OpenStock changes versus proposed workflows; and
- `daily-2026-09-21-6d54e8e9`, retaining generic WATCH guidance and the actual September 22 publication timestamp.

Passing tests prove deterministic static rendering and contract checks only. They do not prove timed usefulness,
comprehension, audio quality, a human listening review, publication approval, live Pages deployment, or subscriber
delivery.
Independent browser and editorial review remain required before any production proposal.
