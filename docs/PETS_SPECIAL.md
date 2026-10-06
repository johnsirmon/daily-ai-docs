# Desktop pets special: research and production handoff

Requested October 6, 2026: research VS Code Pets, OpenAI pets, alternatives,
benefits, overhead, and Google TV compatibility, then publish an ad-hoc podcast.
The user authorized episode publication. This handoff does **not** assert that
audio was generated or that a release or feed item exists.

The reviewed narration contains 1,936 words. It is substantive without padding
to the usual 20–30 minute editorial target. Actual duration awaits generation.

## Findings

| Option | Documented platform/category | Assessment |
| --- | --- | --- |
| [VS Code Pets](https://github.com/tonybaloney/vscode-pets) | VS Code editor extension | Playful companion; no measured productivity improvement established. |
| [OpenAI Pets](https://learn.chatgpt.com/docs/pets) | Supported desktop, web, and terminal interfaces | Activity cues can be useful; the character does not change reasoning. |
| [Desktop Mate](https://store.steampowered.com/app/3301060/Desktop_Mate/) | Steam desktop companion | Rendering and optional character purchases are costs to evaluate. |
| [Desktop Goose](https://samperson.itch.io/desktop-goose) | Windows/macOS entertainment | Deliberate interference makes this better suited to a break. |
| [eSheep](https://github.com/Adrianotiger/desktopPet) | Separate Windows, Android, and macOS routes | Check the particular build rather than assuming universal compatibility. |
| [Stormies](https://github.com/okevino47/stormies) | Community JetBrains/Claude Code visualization | Source-build project; performance claims were not independently reproduced. |
| [Finch](https://finchcare.com/about-finch) | iOS/Android habit companion | Voluntary routine aid; no clinical or coding-performance effect is claimed. |

The selection is illustrative, not exhaustive. No pet software was installed,
no resource benchmarks were performed, and no new subscription was purchased.
The narration proposes a personal comparison with pets visible and hidden;
this is practical advice, not a controlled experiment or a measured result.

For Google TV, no native support was established for the requested editor pet
or floating OpenAI overlay. Google's [casting documentation](https://support.google.com/chromecast/answer/3228332)
supports showing a computer screen on a compatible receiver; displaying the
pet that way is an inference and has not been tested on John's TV. A
[Google Photos screensaver](https://support.google.com/googletv/answer/10070821)
can show pet images. Neither approach installs an interactive pet on the TV.
Check [app availability on the actual television](https://support.google.com/googletv/answer/10050570).

## Evidence and dates

The frozen request uses the default 60-day UTC window. Its dated anchor is the
[October 3 maintenance commit](https://github.com/tonybaloney/vscode-pets/commit/7762b3e49466d688764021f587abde5313cc6cfc)
fixing roll-call fallthrough. The patch was inspected. This is not a claim that
the established pet features were launched in October.

Supporting feature descriptions use bounded excerpts, source-document hashes,
and explicit evergreen snapshot labels. Original feature publication dates
remain unknown. Retrieval dates are not substituted for publication dates.
Each inspected page contributes at most 25 quoted words to the packet.

## Local artifacts

The isolated checkout contains request-local, untracked production files under
`.cache/adhoc/adhoc-ca0991ee7e1762c3e33b8ee7/`:

- `request.json`: authorizing actor, topic, default Notebook provider, publish-now intent, frozen cutoff.
- `narration.txt`: reviewed editorial script; **not** a transcript of generated audio.
- `packet.json`: twelve primary source events mapped to six stories.
- `source-capture-receipts.json`: successful public-page reads, hashes, excerpt sizes.
- `research-notes.md`: research scope, sources, and limitations.
- `notebook-brief.md` and `local-execution.json`: request-bound signed-in Notebook handoff.

The exact-path source-list change admits only the inspected owner pages and
keeps the existing snapshot, hash, public-URL, dated-anchor, and review gates.
Adjacent pages, issue discussions, other owners, and unrelated store products
remain rejected by tests. No daily content or historical RSS item is changed.

## Remaining publication boundaries

The current publisher checks out `main` explicitly. The new exact-page admission
must be merged before a bundle containing these sources can pass its validator.
The earlier delegated authorization allowed feature-branch pushes but expressly
prohibited merges, so this branch is prepared for approval, not merged.

The default Notebook route requires the existing signed-in local browser and
native download. This session exposes no `node_repl`/Computer Use runtime or
signed-in browser tool. No browser generation or download action was claimed.
The ad-hoc skill permits Edge synthesis only for an explicit Edge request; that
provider choice was asked asynchronously and remains pending. If selected,
create a revised Edge request, bind its exact script/voice provenance, master
and validate the audio, then publish only after the source-list merge.

After publication, verify the immutable MP3, public RSS enclosure, and matching
`data/requests` delivery receipt before reporting subscriber-confirmed delivery.

## Verification

`pipeline.adhoc brief` validated the packet and created the Notebook handoff.
The complete offline suite produced **1,593 passed, 3 failed**. All three failing
tests reproduced on unchanged main commit `a16efcb` in a separate baseline
worktree: Gate A's exact manifest bytes and two observer exact-source fixtures.
These are Windows newline/hash fixture issues, not pet-admission regressions.
`pipeline.publish_check`, `pipeline.drift_check`, and `git diff --check` passed.

The live RSS was read again after preparation: HTTP 200, 51 items, latest
publication October 3, and no item for this request. Audio generation and download
attempt counters remain zero. The source-list update is on a feature branch;
the existing publisher and live feed have not been changed.
