# Podcast session lessons

These lessons record observed mistakes and workflow gaps from the September 17,
2026 podcast-improvement session. They are operating guidance, not a claim that
the browser workflow is fully automated.

| What happened | Why it was inefficient or misleading | Rule for future work |
|---|---|---|
| Initial model reviewers lacked repository tools; one returned unsupported architectural claims. | A review sounded more authoritative than its evidence permitted. | Check access first, supply bounded evidence when necessary, and label the review's actual scope. Retract unsupported claims. |
| Several API preview cycles failed before the user redirected generation to Notebook. | Provider availability, model access, and output validation were distinct problems, not one prompt problem. | Bound retries, classify the failure, and stop the superseded route when redirected. |
| Browser download waits timed out while a native Windows Save As dialog needed attention. | Missing automation events were treated too much like missing downloads. | Recognize the web/native boundary. Ask for the Save handoff once; do not trigger duplicate downloads. |
| The user had to click Save. | The transfer was not autonomous. | Record that human step explicitly. Do not claim fully unattended Notebook publication. |
| Initial glob lookups did not locate the saved Windows file. | The Linux and Windows Downloads folders were confused, and a negative lookup was too weak as evidence. | Resolve the Windows known folder, translate its path, and inspect the exact expected file. |
| An unauthenticated media download returned sign-in HTML; a temporary playback URL was inaccessible locally. | HTTP success, extensions, and signed links do not establish valid media. | Validate actual file content and prefer the authenticated UI download. Never extract cookies or bypass access controls. |
| Notebook displayed 6:18 while the file measured about 6:19. | Requested and displayed duration were proxies, not the publication measurement. | Probe and fully decode final bytes, assert the duration budget, and record a checksum. |
| The first reviewed-release workflow rejected a duration metadata difference between local and hosted FFprobe. | Exact equality of a rounded duration was confused with exact media identity. | Bind SHA-256 and byte length exactly; recheck full decode and the duration budget, allowing only a documented, tested MP3-frame-sized metadata tolerance. Never rewrite released media to satisfy a metadata estimate. |
| A constrained prompt still produced an incorrect budget-scope statement. | Prompt compliance cannot be assumed. | Review the transcript against sources before publication; correction must distinguish a member's budget from the organization's overall budget. |
| Simplified web extraction omitted a managed-user eligibility qualification. | Missing text in a parser output could have been mistaken for an absent source claim. | Check the relevant primary-source HTML or visible page before concluding a qualification is unsupported. |
| An old skill referenced a nonexistent workflow filename and legacy commands. | Remembered documentation was mistaken for current executable configuration. | Discover actual workflow filenames and current CLI help before running or documenting commands. |

## Reusable procedures

- [Notebook generation, download, review, and publication](../.github/skills/notebook-podcast/SKILL.md)
- [Evidence-led repository and model review](../.github/skills/evidence-led-review/SKILL.md)
- [Current operations](OPERATIONS.md)

## Non-negotiable publication gates

1. Explicit publication authorization and honest provider/review provenance.
2. Source-backed spoken claims, with research limitations and material corrections.
3. Original input preserved; final publication bytes fully decoded and measured.
4. A new immutable release and GUID; no replacement of existing subscriber media.
5. Shared publisher concurrency, remote media verification, valid RSS, and public
   subscriber-facing confirmation before advancing state.

Neither successful generation nor passing unit tests proves all five gates.
