# Human-in-the-Loop Review Guide

## Guidance Obsolescence

| Section | Review trigger | Last validated |
|---------|----------------|----------------|
| Review workflow | doc_updater.py changes | 2025-06 |
| Feedback format | feedback_collector.py changes | 2025-06 |
| Rating criteria | Team AI policy change | 2025-06 |

This guide explains how to review AI-generated documentation updates and provide feedback
that the system uses to **self-tune** future runs.

---

## Why Your Feedback Matters

Every time you review an update and rate it, your comments and corrections are saved to
`feedback/feedback_log.json`. The next time `doc_updater.py` runs, it automatically reads
this history and injects it into the AI prompts — so the system continuously improves based
on your input.

---

## Quick-Start: Review in 60 Seconds

After a daily update run, check whether there are pending reviews:

```bash
python feedback_collector.py list
```

Then start the guided review session:

```bash
python feedback_collector.py review
# or via the updater shortcut:
python doc_updater.py --review
```

You'll be prompted to:

1. View a preview of the updated document (optional)
2. Rate **accuracy** on a 1–5 scale
3. Rate **usefulness** on a 1–5 scale
4. Leave free-text comments and corrections (optional)

The whole session takes under two minutes per document.

---

## Command Reference

| Command | Description |
| ------- | ----------- |
| `python feedback_collector.py` | Start interactive review (same as `review`) |
| `python feedback_collector.py review` | Start interactive review session |
| `python feedback_collector.py list` | Show documents pending review |
| `python feedback_collector.py summary --doc <file>` | Show aggregate feedback for a document |
| `python feedback_collector.py add ...` | Add feedback non-interactively (see below) |
| `python doc_updater.py --review` | Review shortcut from the main updater |

### Non-interactive feedback (for scripting)

```bash
python feedback_collector.py add \
  --doc "ChatGPT-Models-Prompting-Guide.md" \
  --run-id "20250222_090012" \
  --accuracy 4 \
  --usefulness 5 \
  --comments "Good overall, pricing tables are accurate" \
  --corrections "GPT-4o mini context window is 128k, not 64k"
```

---

## GitHub Issues (Async Feedback)

If you prefer to leave feedback asynchronously, open a **GitHub Issue** using the
**📝 Document Feedback** template:

1. Go to **Issues → New Issue**
2. Select **📝 Document Feedback**
3. Fill in the document name, run ID, ratings, and any corrections
4. Submit the issue

A maintainer can then apply the feedback with:

```bash
python feedback_collector.py add \
  --doc "<document>" \
  --run-id "<run-id>" \
  --accuracy <1-5> \
  --usefulness <1-5> \
  --comments "<issue comments>"
```

---

## How Self-Tuning Works

```text
Daily run ──► AI generates updated docs
                │
                ▼
       review_request_<id>.json  ◄── you run: python feedback_collector.py review
                │
                ▼
       feedback/feedback_log.json  ◄── ratings + corrections stored here
                │
                ▼
       Next daily run ──► feedback injected into AI prompts ──► better output
```

The more feedback you provide, the more the system learns your preferences for:

- **Depth** – how technical the content should be
- **Structure** – which sections are most valuable
- **Accuracy** – which facts the AI tends to get wrong
- **Tone** – formal vs. conversational

---

## Feedback File Location

All feedback is stored in `feedback/feedback_log.json`. This file is committed to the
repository so feedback is preserved across environments and contributors.

```text
feedback/
└── feedback_log.json   # All ratings, comments, and corrections
```

---

## Tips for Effective Feedback

- **Be specific in corrections** — "Section 3 pricing is wrong" is less helpful than
  "GPT-4o input price is $2.50/1M tokens, not $5.00."
- **Rate consistently** — A 3/5 should mean "acceptable but improvable" every time.
- **Use comments for patterns** — If the AI keeps adding irrelevant content, say so:
  "Stop adding 'coming soon' sections for unconfirmed features."
- **Review promptly** — Feedback from the most recent run has the highest impact.
