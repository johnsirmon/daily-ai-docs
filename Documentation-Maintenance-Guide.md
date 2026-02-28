# Auto-Update Options for Your Repo

## Guidance Obsolescence

| Section | Review trigger | Last validated |
|---------|----------------|----------------|
| GitHub Actions setup | Actions runner update | 2025-06 |
| Automation options | New CI/CD tooling available | 2025-06 |
| API integration steps | OpenAI API change | 2025-06 |

## Option 1: GitHub Actions with Manual Trigger
Add this button to your README.md:

```markdown
[![Update Cheat Sheet](https://img.shields.io/badge/🔄_Update-Cheat_Sheet-blue?style=for-the-badge)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/update-cheatsheet.yml)

**Click to manually trigger an AI-powered update check** 
```

Then create `.github/workflows/update-cheatsheet.yml`:

```yaml
name: Update Cheat Sheet
on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 9 * * 1'  # Weekly on Monday 9AM
    
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Check for updates
      run: |
        echo "This would call OpenAI API to check document currency"
        echo "Then create a PR with suggested changes"
```

## Option 2: Simple Issue Template
Create `.github/ISSUE_TEMPLATE/update-request.md`:

```markdown
---
name: 📝 Update Request
about: Request an update to the cheat sheet
title: '[UPDATE] Cheat Sheet Needs Review'
labels: ['documentation', 'update-needed']
---

## What needs updating?
- [ ] New model capabilities
- [ ] Deprecated features  
- [ ] New techniques
- [ ] Research findings

**AI Prompt for Review:**
```
[Include your maintenance prompt here]
```

**Detected changes:**
<!-- Describe what triggered this update request -->
```

## Option 3: Simple Links in Markdown
Add these to your main document:

```markdown
---
**🔄 Quick Actions:**
- [📝 Suggest Edit](https://github.com/YOUR_USERNAME/YOUR_REPO/edit/main/July2025CheatSheet.md) 
- [🐛 Report Issue](https://github.com/YOUR_USERNAME/YOUR_REPO/issues/new?template=update-request.md)
- [🤖 Run AI Check](https://chatgpt.com/?q=Check%20this%20document%20for%20updates)
---
```

**Recommendation:** Use Option 3 for simplicity - it gives users direct links to edit or report issues.
