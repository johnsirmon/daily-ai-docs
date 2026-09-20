# Podcast presentation

## What listeners should see

- **Show cover:** a high-contrast navy, mint, and white title with an original sculptural waveform, not a detailed poster.
  There is no small-print slogan. The same recognizable cover applies to the entire feed.
- **Episode title:** the subject first, not the show name and publication date repeated on every row.
  The editorial target is at most 90 characters, not an Apple or CarPlay visibility guarantee.
- **Description:** an episode-specific introduction before the detailed notes. Corrections, recommendations,
  research qualifications, coverage gaps, and public source links remain available.
- **Expanded notes:** plain text in RSS `description` and `itunes:summary`; escaped paragraphs, line breaks, and
  HTTPS links in `content:encoded`. Untrusted source HTML is never copied into executable markup.
- **Historical editions:** reviewed display copy is separate from the accepted audio and manifest. Weekly entries
  describe the publication-time digest, not a newly reviewed recording.

The show cover remains the fallback; selected episodes can use unique, text-free topic illustrations.
Apple recommends avoiding logos and text in optional episode artwork. This is an operator-reviewed choice,
not a bulk or automatic generation step for every episode.

## Evidence and compatibility

`pipeline.podcast_metadata.manifest_presentation` derives future display copy from accepted story headlines and
changes. It does not call a model, change story selection, or add new product claims. Long extractive previews
end with an ellipsis; complete notes remain below. Reviewed editions retain their edition label in the description.

`data/podcast-metadata.json` contains reviewed titles and opening summaries for the retained back catalog.
Each copy entry cites an immutable public Git commit permalink to its original manifest, digest, or feed topic.
Do not substitute today's documentation or a recent release note for what the historical episode covered.
No listening review is implied by a digest-backed description.

Schema 1 catalog entries may add `image_url` to the existing `title`, `summary`, and `evidence_url` fields.
An entry containing only `image_url` is also supported: refresh preserves its existing copy; new daily/special episodes
use the accepted manifest's derived copy. An exact future GUID may reserve art before publication; refresh only
visits existing RSS items and never creates the reserved episode. Partial copy fields and unknown fields fail closed.
Only `https://johnsirmon.github.io/daily-ai-docs/assets/episodes/<filename>.jpg` is supported. Filenames use lowercase
letters, digits, hyphens, and underscores; query strings, credentials, fragments, escapes, subdirectories, and traversal
are rejected. Use a unique versioned filename for each revision and retain previously referenced files.
The repository deliberately supports RGB JPEG only (square, 1400-3000 pixels, under 1 MB), narrower than Apple's
JPG/PNG allowance. No change to `EpisodeManifest` serialization or existing audio provenance is needed.

All manifest versions remain unchanged:

| Stage | Presentation behavior |
| --- | --- |
| Collection, selection, schema 1-4 validation, evidence archive | Unchanged; accepted evidence remains authoritative |
| Narration, transcript, mastering, release assets | Unchanged; no regeneration or retagging of published MP3s |
| Finalize and new candidate feed | Derive copy from the manifest, apply optional reviewed catalog copy/art |
| Historical RSS refresh | Apply reviewed copy/art; retain daily notes, archival links, and existing item art |
| Delivery receipts, state, confirmation, recovery | Unchanged; still bind GUID, date, enclosure, and audio hash |

The migration preserves feed order, GUIDs, publication dates, enclosure URLs/types/lengths, durations, and other
item tags. It never writes manifests, receipts, state, or release assets. It validates available manifests against
feed media, refuses missing archival evidence, checks the complete replacement before an atomic write, and refuses
to overwrite a feed changed while it was running. Repeating the refresh produces identical output.

## Updating or regenerating

From the repository root, with the locked environment:

```bash
# Recreate the current RGB JPEG; keeps the previous filename available for cached feeds.
uv run --python 3.11 --with-requirements requirements.lock python scripts/generate_artwork.py

# Validate the catalog and preview whether RSS would change, without writing.
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.podcast_metadata

# Explicit display-only refresh of existing entries. Does not publish an episode.
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.podcast_metadata --write

# Art changes only: preserve every existing item and channel text field.
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.podcast_metadata --artwork-only --write

# Local acceptance gates.
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.publish_check
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.drift_check
```

The current image is `assets/podcast-cover-v3.jpg`: 3000 x 3000, RGB, JPEG, no transparency, under the repository's
1 MB budget. `scripts/generate_artwork.py` uses installed DejaVu Sans Bold or Arial Bold, measures text width,
and keeps the title within a generous safe margin. Glyph shapes may vary between operating systems.
The generated background is retained in `assets/podcast-background-v3.png`; all title text is rendered
locally for exact spelling and reproducibility. The 594-pixel background is an image-only crop of the
loaded browser rendering after Save did not expose a download. It is a rendered pixel capture, not
original-download bytes; the final title typography is rendered directly at 3000 pixels.
The public design brief requested a midnight-navy square,
ample empty space for the title, and a mint/ice-blue sculptural waveform in the bottom-right quadrant,
without text, logos, robots, circuitry, or small details. Earlier cover URLs remain hosted for cached feeds.
The show name and all historical audio identities are unchanged.
When changing the cover design again, use a new filename and update the feed default and artwork checks.
Both Pages paths copy the versioned and previous JPEGs so cached feeds retain working image URLs.

For selected episode art, preserve the authenticated browser export privately and record provider/browser provenance;
do not substitute an API generation. Label rendered captures honestly if original bytes were unavailable.
Review the square source, including a thumbnail view, before converting it with the existing environment:

```powershell
.\.venv\Scripts\python.exe scripts\generate_artwork.py `
  --episode-source .cache\episode-artwork\reviewed-source.png `
  --output assets\episodes\topic-v1.jpg
```

This path adds no typography, resizes to 3000 pixels, converts to RGB, and strips source metadata. It uses fixed
JPEG quality 85 with optimization and chroma subsampling. It fails rather than silently cropping a non-square source,
flattening transparency, exceeding 1 MB, or overwriting an existing destination. Review a simpler source if it exceeds
the size budget. The 1400-pixel minimum applies to final exports, not square source images.
Source PNGs and private staging are never copied into the Pages artifact. Refresh validates all
configured artwork (including pending reservations) before replacing RSS; `publish_check` validates local feed/catalog
assets, while live delivery validates the latest episode image's HTTP status, JPEG content type, and decoded bytes.
Older entries' art survives load/render/prepend and recovery; omitted `image_url` does not remove existing art.

Run refreshes from up-to-date publication history. Inspect the diff before merging generated RSS.
Do not blindly rebase a stale generated feed over a newer episode; rerun the refresh against current `main`.
The normal Pages workflow deploys the changed feed/artwork after merge. The publisher also ships those assets
on its next normal publication. Local generation is **not** proof that the public feed or Apple has refreshed.

Rollback is limited to display copy: revert the metadata, feed, and cover URL together, keeping all episode identities
and audio untouched. Leave previously referenced image files hosted. Never roll publication state backward.

## Apple guidance checked September 19, 2026

| Topic | Verified guidance | Application here |
| --- | --- | --- |
| [Show Cover][show] | Required; prominent title, contrast, small-size legibility | Simplified typography |
| [Episode Art][episode] | Optional; show-cover fallback; avoid logos and text | Reviewed topic art or show fallback |
| [Artwork][artwork] | RGB JPG/PNG, 1400-3000 pixels for RSS; new URL for changed art | Versioned 3000-pixel JPEG |
| [Presentation][present] | Omit repeated show name/date; lead with important information | Topic-first copy |
| [Search][search] | Specific, unique titles; avoid repeated titles and emojis | No ranking promise |
| [Descriptions][create] | Describe the episode to potential listeners | Summary before detailed evidence |
| [RSS requirements][rss] | Episode GUID never changes | Metadata-only migration, not re-publication |
| [Metadata][metadata] | Change RSS-hosted metadata at the host, not in Connect | Update RSS and deploy Pages |
| [Refresh][refresh] | Check Last Refresh; request Refresh Feed if needed | Verify public RSS first |
| [CarPlay][carplay] | iOS renders templates; screen sizes vary | No control of fonts, crop, or wrapping |

Apple says metadata/artwork changes can take up to 24 hours to appear. If the public feed has the new content but
Apple does not, check the show is Published and inspect **Last Refresh** in Apple Podcasts Connect, then use
**Refresh Feed** if needed. Existing downloads/client caches can differ from a newly fetched episode.
Verify on the actual phone and CarPlay display after deployment; a desktop thumbnail check is not a CarPlay test.

[show]: https://podcasters.apple.com/support/5514-show-cover-template
[episode]: https://podcasters.apple.com/support/5516-episode-art-template
[artwork]: https://podcasters.apple.com/support/902-troubleshooting-artwork-issues
[present]: https://podcasters.apple.com/support/867-featured-present-your-podcast
[search]: https://podcasters.apple.com/support/3686-search-on-apple-podcasts
[create]: https://podcasters.apple.com/support/825-how-to-create-an-episode
[rss]: https://podcasters.apple.com/support/823-podcast-requirements
[metadata]: https://podcasters.apple.com/support/832-podcast-metadata
[refresh]: https://podcasters.apple.com/support/838-refresh-a-podcast
[carplay]: https://developer.apple.com/design/human-interface-guidelines/carplay
