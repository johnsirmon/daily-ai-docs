# Security Policy

## Supported Versions

The pipeline code in this repository is continuously updated on the `main` branch.
Security fixes are applied to `main` only.

| Branch | Supported |
|--------|-----------|
| `main` | ✅ Yes |
| older branches | ❌ No |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use GitHub's private vulnerability reporting instead:

👉 [Report a vulnerability privately](https://github.com/johnsirmon/daily-ai-docs/security/advisories/new)

Include in your report:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

You will receive a response within **7 days**. If the issue is confirmed, a fix will be
prepared and released as quickly as possible. You will be credited in the release notes
unless you prefer to remain anonymous.

## Security Best Practices for Forks

If you fork this repository and run the workflow yourself:

- **Never commit API keys or tokens** — use GitHub Actions secrets instead
- The pipeline only needs the built-in `GITHUB_TOKEN`; do not grant it unnecessary scopes
- Treat any `GITHUB_TOKEN` with `contents: write` access as a sensitive credential

## Contact

**Security reports**: [Open a private vulnerability report](https://github.com/johnsirmon/daily-ai-docs/security/advisories/new)  
**General questions**: [Open an issue](https://github.com/johnsirmon/daily-ai-docs/issues)  
**Maintainer**: [@johnsirmon](https://github.com/johnsirmon)
