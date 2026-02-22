#!/usr/bin/env python3
"""
Human-in-the-Loop Feedback Collector for AI Documentation
Allows reviewers to rate and correct AI-generated documentation updates so
the system can self-tune on subsequent runs.
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_FEEDBACK_FILE = "feedback/feedback_log.json"
DEFAULT_VERSIONS_DIR = "versions"


class FeedbackCollector:
    """Collects, stores, and retrieves human feedback on AI-generated document updates."""

    def __init__(self, feedback_file: str = DEFAULT_FEEDBACK_FILE,
                 versions_dir: str = DEFAULT_VERSIONS_DIR):
        self.feedback_file = Path(feedback_file)
        self.versions_dir = Path(versions_dir)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict:
        if self.feedback_file.exists():
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"entries": [], "last_updated": None}

    def _save(self):
        self._data["last_updated"] = datetime.now().isoformat()
        with open(self.feedback_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    # ------------------------------------------------------------------
    # Core feedback operations
    # ------------------------------------------------------------------

    def add_feedback(self, doc_name: str, run_id: str, accuracy_rating: int,
                     usefulness_rating: int, comments: str = "",
                     corrections: str = "") -> Dict:
        """Record a single feedback entry and persist it."""
        entry = {
            "id": f"{run_id}_{doc_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "doc_name": doc_name,
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "accuracy_rating": accuracy_rating,    # 1–5
            "usefulness_rating": usefulness_rating,  # 1–5
            "comments": comments,
            "corrections": corrections,
            "applied": False,
        }
        self._data["entries"].append(entry)
        self._save()
        return entry

    def get_feedback_for_doc(self, doc_name: str, limit: int = 5) -> List[Dict]:
        """Return the most recent feedback entries for a document."""
        entries = [e for e in self._data["entries"] if e["doc_name"] == doc_name]
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_feedback_summary(self, doc_name: str) -> str:
        """Return a human-readable summary of past feedback suitable for injection
        into AI prompts so the system can self-tune."""
        entries = self.get_feedback_for_doc(doc_name)
        if not entries:
            return "No previous human feedback available for this document."

        avg_accuracy = sum(e["accuracy_rating"] for e in entries) / len(entries)
        avg_usefulness = sum(e["usefulness_rating"] for e in entries) / len(entries)

        lines = [
            f"HUMAN FEEDBACK HISTORY ({len(entries)} review(s)):",
            f"  Average accuracy rating : {avg_accuracy:.1f}/5",
            f"  Average usefulness rating: {avg_usefulness:.1f}/5",
            "  Recent comments and corrections:",
        ]
        for entry in entries[:3]:
            if entry.get("comments"):
                lines.append(f"    - Comment   : {entry['comments']}")
            if entry.get("corrections"):
                lines.append(f"    - Correction: {entry['corrections']}")
        lines.append(
            "Use this feedback to improve accuracy, depth, and relevance in the updated document."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Pending review discovery
    # ------------------------------------------------------------------

    def list_pending_reviews(self) -> List[Dict]:
        """Return review items that have not yet received feedback."""
        reviewed_keys = {
            (e["run_id"], e["doc_name"]) for e in self._data["entries"]
        }
        pending = []
        if not self.versions_dir.exists():
            return pending
        review_files = sorted(
            self.versions_dir.glob("review_request_*.json"), reverse=True
        )[:20]
        for review_file in review_files:
            try:
                with open(review_file, "r", encoding="utf-8") as f:
                    review_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            run_id = review_data.get("run_id", "")
            for doc in review_data.get("documents", []):
                key = (run_id, doc["doc_name"])
                if key not in reviewed_keys:
                    pending.append({
                        "run_id": run_id,
                        "doc_name": doc["doc_name"],
                        "version_file": doc.get("version_file", ""),
                        "analysis": doc.get("analysis", "")[:300],
                        "review_file": str(review_file),
                    })
        return pending

    # ------------------------------------------------------------------
    # Interactive CLI review
    # ------------------------------------------------------------------

    def interactive_review(self):
        """Run a guided interactive review session in the terminal."""
        pending = self.list_pending_reviews()
        if not pending:
            print("✅ No pending document reviews – all updates have been reviewed!")
            return

        print(f"\n📋 {len(pending)} document(s) pending review\n")

        for i, item in enumerate(pending, 1):
            print("=" * 60)
            print(f"[{i}/{len(pending)}] Review: {item['doc_name']}")
            print(f"Run ID : {item['run_id']}")
            if item["analysis"]:
                print(f"Summary: {item['analysis']}...")

            version_path = Path(item["version_file"])
            if version_path.exists():
                show = input("\nShow document preview? (y/N): ").strip().lower()
                if show == "y":
                    with open(version_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    print("\n" + "-" * 40 + " DOCUMENT PREVIEW " + "-" * 40)
                    print(content[:2000])
                    if len(content) > 2000:
                        print(f"\n[…{len(content) - 2000} more characters…]")
                    print("-" * 98)

            print("\nPlease rate this document update:")
            accuracy = self._prompt_rating("Accuracy (1=very inaccurate … 5=perfectly accurate)")
            usefulness = self._prompt_rating("Usefulness  (1=not useful … 5=very useful)     ")

            comments = input("General comments (Enter to skip): ").strip()
            corrections = input("Specific corrections needed (Enter to skip): ").strip()

            entry = self.add_feedback(
                doc_name=item["doc_name"],
                run_id=item["run_id"],
                accuracy_rating=accuracy,
                usefulness_rating=usefulness,
                comments=comments,
                corrections=corrections,
            )
            print(f"\n✅ Feedback saved (ID: {entry['id']})")

            if i < len(pending):
                cont = input("\nContinue to next review? (Y/n): ").strip().lower()
                if cont == "n":
                    break

        print("\n🎉 Review session complete! Feedback will improve the next run.")

    @staticmethod
    def _prompt_rating(label: str) -> int:
        while True:
            try:
                val = int(input(f"{label}: ").strip())
                if 1 <= val <= 5:
                    return val
            except ValueError:
                pass
            print("  Please enter a number between 1 and 5.")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Human-in-the-Loop Feedback Collector for AI Documentation"
    )
    parser.add_argument("--feedback-file", default=DEFAULT_FEEDBACK_FILE,
                        help="Path to feedback log JSON file")
    parser.add_argument("--versions-dir", default=DEFAULT_VERSIONS_DIR,
                        help="Path to versions directory")

    sub = parser.add_subparsers(dest="command")

    # review – interactive terminal session
    sub.add_parser("review", help="Start an interactive review session")

    # add – non-interactive feedback from CLI flags
    add_p = sub.add_parser("add", help="Add feedback without interactive prompts")
    add_p.add_argument("--doc", required=True, help="Document filename")
    add_p.add_argument("--run-id", required=True, help="Run ID from check_results JSON")
    add_p.add_argument("--accuracy", type=int, required=True, choices=range(1, 6),
                       metavar="1-5", help="Accuracy rating (1–5)")
    add_p.add_argument("--usefulness", type=int, required=True, choices=range(1, 6),
                       metavar="1-5", help="Usefulness rating (1–5)")
    add_p.add_argument("--comments", default="", help="General comments")
    add_p.add_argument("--corrections", default="", help="Specific corrections needed")

    # list – show pending reviews
    sub.add_parser("list", help="List documents awaiting review")

    # summary – show aggregate feedback for a document
    summary_p = sub.add_parser("summary", help="Show feedback summary for a document")
    summary_p.add_argument("--doc", required=True, help="Document filename")

    args = parser.parse_args()
    collector = FeedbackCollector(args.feedback_file, args.versions_dir)

    if args.command == "add":
        entry = collector.add_feedback(
            doc_name=args.doc,
            run_id=args.run_id,
            accuracy_rating=args.accuracy,
            usefulness_rating=args.usefulness,
            comments=args.comments,
            corrections=args.corrections,
        )
        print(f"✅ Feedback saved (ID: {entry['id']})")

    elif args.command == "list":
        pending = collector.list_pending_reviews()
        if pending:
            print(f"📋 {len(pending)} pending review(s):")
            for item in pending:
                print(f"  - {item['doc_name']}  (run: {item['run_id']})")
        else:
            print("✅ No pending reviews.")

    elif args.command == "summary":
        print(f"\nFeedback Summary — {args.doc}")
        print(collector.get_feedback_summary(args.doc))

    else:
        # Default: interactive review
        collector.interactive_review()


if __name__ == "__main__":
    main()
