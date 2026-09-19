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

We intentionally use the show-cover fallback rather than putting dense titles on 42 separate episode images.
Apple recommends avoiding logos and text in optional episode artwork. Unique, text-free illustrations can be
added later if there is a meaningful visual subject; they are not required to make titles and notes useful.

## Evidence and compatibility

`pipeline.podcast_metadata.manifest_presentation` derives future display copy from accepted story headlines and
changes. It does not call a model, change story selection, or add new product claims. Long extractive previews
end with an ellipsis; complete notes remain below. Reviewed editions retain their edition label in the description.

`data/podcast-metadata.json` contains reviewed titles and opening summaries for the retained back catalog.
Each entry cites an immutable public Git commit permalink to its original manifest, digest, or feed topic.
Do not substitute today's documentation or a recent release note for what the historical episode covered.
No listening review is implied by a digest-backed description.

All manifest versions remain unchanged:

| Stage | Presentation behavior |
| --- | --- |
| Collection, selection, schema 1-4 validation, evidence archive | Unchanged; accepted evidence remains authoritative |
| Narration, transcript, mastering, release assets | Unchanged; no regeneration or retagging of published MP3s |
| Finalize and new candidate feed | Derive title and introductory description from the validated manifest |
| Historical RSS refresh | Apply reviewed copy; retain full daily show notes and archival evidence links |
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
| [Episode Art][episode] | Optional; show-cover fallback; avoid logos and text | Consistent show cover |
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
