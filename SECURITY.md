# Security Policy

## Scope

This repository's active development branch is `main`. Report security concerns against the current daily podcast
pipeline, weekly YouTube discovery, dependencies, or publication workflows. There is no separate maintained release
series or promised backport schedule for older branches.

The repository, GitHub Pages feed, release assets, and committed episode manifests are public. They must not contain
private repository data, internal topics, credentials, or private source excerpts.

## Reporting a vulnerability

**GitHub private vulnerability reporting is currently disabled for this repository. No dedicated private reporting
channel is currently documented.** Do not assume that a GitHub issue, pull request, or advisory link is confidential.

To request a secure way to share a report, open a **minimal, non-sensitive**
[issue](https://github.com/johnsirmon/daily-ai-docs/issues) addressed to
[@johnsirmon](https://github.com/johnsirmon), asking the maintainer to arrange a private channel or enable GitHub private
vulnerability reporting. This initial request is public: do not include vulnerability details, exploit code, credentials,
private URLs, or sensitive logs. Wait until the maintainer confirms a private channel before sending those details.

Once a private channel has been confirmed, include:

- The affected component and commit or branch.
- A description of the potential impact.
- Safe reproduction steps and redacted evidence.
- A suggested fix, if available, and your disclosure or attribution preference.

Do not test against other users' data or disrupt the live feed. Response and remediation times are not guaranteed.
For ordinary bugs and general questions, use the repository's public issues without sensitive information.

## Credentials and workflow safety

- Never commit API keys or tokens. Store workflow credentials in GitHub Actions secrets and avoid printing them in logs.
- `GITHUB_TOKEN` is for GitHub collection and publication, not model inference. Keep permissions scoped to each job:
  tests need read access, publishers need repository writes, and Pages deployment needs Pages and OIDC permissions.
  Do not grant publishing permissions or secrets to untrusted pull request code.
- Weekly video discovery requires `YOUTUBE_API_KEY`. Restrict the Google Cloud key to YouTube Data API v3 and store it
  only as an Actions secret. CI rejects tracked Google API-key patterns, but this is not a comprehensive secret scan.
- `TTS_PROVIDER=openai` requires `OPENAI_API_KEY`; the default Edge path uses no key. Optional synthesis uses `AI_API_KEY`
  or `OPENAI_API_KEY`. `EXA_API_KEY` is only for public ad-hoc research; ad-hoc publication is paused.
- If a credential is exposed in a commit, issue, log, or retained chat, revoke or rotate it at the issuing provider,
  update the corresponding Actions secret, and remove the disclosed value where possible. Deleting text alone does not
  revoke a credential. For a Google Cloud key, rotate it in Cloud Console and delete the old key.
- Treat fetched text as untrusted data. Use only public source evidence and do not commit full YouTube transcripts.
- Preserve publication verification: validate audio and RSS before publishing, verify subscriber-facing delivery before
  advancing state, and never replace immutable release audio behind an existing episode GUID or enclosure URL.

See [operations and setup](docs/OPERATIONS.md#github-setup) for the current credential configuration and
[failure recovery](docs/OPERATIONS.md#failure-recovery) for publication incidents.
