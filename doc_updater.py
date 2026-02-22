#!/usr/bin/env python3
"""
AI Documentation Auto-Updater
Monitors AI platforms for changes and updates documentation automatically.
"""

import os
import json
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import openai
from anthropic import Anthropic
import argparse
import logging

from feedback_collector import FeedbackCollector

class AIDocumentationUpdater:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the updater with configuration."""
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.setup_ai_clients()
        self.docs_dir = Path(self.config.get("docs_directory", "."))
        self.versions_dir = Path(self.config.get("versions_directory", "versions"))
        self.versions_dir.mkdir(exist_ok=True)
        # Human-in-the-loop feedback integration
        human_review_cfg = self.config.get("human_review", {})
        feedback_file = human_review_cfg.get("feedback_file", "feedback/feedback_log.json")
        self.feedback = FeedbackCollector(
            feedback_file=feedback_file,
            versions_dir=str(self.versions_dir),
        )
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        default_config = {
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "docs_directory": ".",
            "versions_directory": "versions",
            "check_urls": [
                "https://platform.openai.com/docs/models",
                "https://docs.anthropic.com/claude/docs",
                "https://github.com/openai/openai-cookbook"
            ],
            "documents": [
                "ChatGPT-Models-Prompting-Guide.md",
                "Anthropic-Claude-Models-Guide.md",
                "AI-Platform-Comparison-Guide.md",
                "AI-Terminal-CLI-Guide.md",
                "ChatGPT-Complete-Reference-Guide.md"
            ]
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        else:
            # Create default config file
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('doc_updater.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_ai_clients(self):
        """Initialize AI API clients."""
        if self.config["openai_api_key"]:
            self.openai_client = openai.OpenAI(api_key=self.config["openai_api_key"])
        if self.config["anthropic_api_key"]:
            self.anthropic_client = Anthropic(api_key=self.config["anthropic_api_key"])
    
    def fetch_latest_info(self) -> Dict[str, str]:
        """Fetch latest information from AI platforms."""
        latest_info = {}
        
        # Check OpenAI documentation
        try:
            self.logger.info("Fetching latest OpenAI information...")
            openai_prompt = """
            Research the latest OpenAI models, features, and prompt engineering best practices.
            Focus on: new models, changed capabilities, updated pricing, new features, deprecated models.
            Return a structured summary of significant changes since July 2025.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an AI research assistant specializing in tracking OpenAI updates and changes."},
                    {"role": "user", "content": openai_prompt}
                ],
                temperature=0.1
            )
            latest_info["openai"] = response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Error fetching OpenAI info: {e}")
            latest_info["openai"] = "Error fetching data"
        
        # Check Anthropic documentation
        try:
            self.logger.info("Fetching latest Anthropic information...")
            claude_prompt = """
            Research the latest Claude models, features, and prompt engineering best practices.
            Focus on: new models, changed capabilities, updated pricing, new features, Claude Code updates.
            Return a structured summary of significant changes since July 2025.
            """
            
            if hasattr(self, 'anthropic_client'):
                # This would be the actual Anthropic API call
                # For now, using OpenAI to research Anthropic
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an AI research assistant specializing in tracking Anthropic Claude updates and changes."},
                        {"role": "user", "content": claude_prompt}
                    ],
                    temperature=0.1
                )
                latest_info["anthropic"] = response.choices[0].message.content
                
        except Exception as e:
            self.logger.error(f"Error fetching Anthropic info: {e}")
            latest_info["anthropic"] = "Error fetching data"
        
        return latest_info
    
    def analyze_changes(self, doc_path: Path, latest_info: Dict[str, str]) -> Tuple[bool, str]:
        """Analyze if document needs updating based on latest information."""
        if not doc_path.exists():
            return False, "Document not found"
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        # Determine which platform this document covers
        platform = "general"
        if "chatgpt" in doc_path.name.lower() or "openai" in doc_path.name.lower():
            platform = "openai"
        elif "claude" in doc_path.name.lower() or "anthropic" in doc_path.name.lower():
            platform = "anthropic"
        
        # Inject previous human feedback so the AI can self-tune
        feedback_context = self.feedback.get_feedback_summary(doc_path.name)

        # Create analysis prompt
        analysis_prompt = f"""
        CURRENT DOCUMENT:
        {current_content[:8000]}...
        
        LATEST INFORMATION ({platform.upper()}):
        {latest_info.get(platform, "No specific updates")}
        
        {feedback_context}
        
        ANALYSIS TASK:
        1. Compare the current document with the latest information
        2. Identify any outdated information, new features, or changed recommendations
        3. Determine if significant updates are needed (not just minor wording changes)
        
        Return:
        - NEEDS_UPDATE: true/false
        - REASON: Brief explanation of why update is needed
        - PRIORITY: high/medium/low
        - CHANGES: List of specific changes needed
        
        Only return NEEDS_UPDATE: true for significant changes that affect user guidance.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing AI documentation for accuracy and relevance."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1
            )
            
            analysis = response.choices[0].message.content
            needs_update = "NEEDS_UPDATE: true" in analysis.upper()
            
            return needs_update, analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing changes for {doc_path}: {e}")
            return False, f"Analysis error: {e}"
    
    def create_updated_document(self, doc_path: Path, latest_info: Dict[str, str], analysis: str) -> str:
        """Create an updated version of the document."""
        with open(doc_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        platform = "general"
        if "chatgpt" in doc_path.name.lower() or "openai" in doc_path.name.lower():
            platform = "openai"
        elif "claude" in doc_path.name.lower() or "anthropic" in doc_path.name.lower():
            platform = "anthropic"
        
        # Inject previous human feedback for self-tuning
        feedback_context = self.feedback.get_feedback_summary(doc_path.name)

        update_prompt = f"""
        CURRENT DOCUMENT:
        {current_content}
        
        LATEST INFORMATION ({platform.upper()}):
        {latest_info.get(platform, "No specific updates")}
        
        ANALYSIS RESULTS:
        {analysis}
        
        {feedback_context}
        
        UPDATE TASK:
        Create an updated version of this document that:
        1. Maintains the same structure and format
        2. Updates outdated information with current facts
        3. Adds new relevant information where appropriate
        4. Preserves the document's style and tone
        5. Updates the version date to {datetime.now().strftime('%Y-%m-%d')}
        
        Return the complete updated document in markdown format.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert technical writer specializing in AI documentation."},
                    {"role": "user", "content": update_prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Error creating updated document for {doc_path}: {e}")
            return ""
    
    def save_version(self, doc_path: Path, content: str, version_info: Dict) -> Path:
        """Save a versioned copy of the document."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_name = doc_path.stem
        version_filename = f"{doc_name}_v{timestamp}.md"
        version_path = self.versions_dir / version_filename
        
        # Save the document
        with open(version_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Save version metadata
        metadata = {
            "original_file": str(doc_path),
            "version_timestamp": timestamp,
            "changes_detected": version_info.get("analysis", ""),
            "update_reason": version_info.get("reason", ""),
            "priority": version_info.get("priority", "medium")
        }
        
        metadata_path = self.versions_dir / f"{doc_name}_v{timestamp}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return version_path
    
    def update_original_document(self, doc_path: Path, updated_content: str):
        """Update the original document with new content."""
        # Create backup
        backup_path = doc_path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md')
        doc_path.rename(backup_path)
        
        # Write updated content
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        self.logger.info(f"Updated {doc_path}, backup saved as {backup_path}")
    
    def generate_review_request(self, run_id: str, results: Dict[str, Dict]):
        """Write a review_request JSON file so humans know which updates need review."""
        docs_needing_review = []
        for doc_name, info in results.items():
            if info.get("needs_update") and info.get("version_created"):
                docs_needing_review.append({
                    "doc_name": doc_name,
                    "version_file": info.get("version_created", ""),
                    "analysis": info.get("analysis", "")[:500],
                    "timestamp": info.get("timestamp", ""),
                })
        if not docs_needing_review:
            return None
        review_request = {
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(),
            "documents": docs_needing_review,
            "review_instructions": (
                "Run 'python feedback_collector.py review' to start an interactive review, "
                "or 'python feedback_collector.py add --doc <name> --run-id <id> "
                "--accuracy <1-5> --usefulness <1-5>' to add feedback non-interactively."
            ),
        }
        review_path = self.versions_dir / f"review_request_{run_id}.json"
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(review_request, f, indent=2)
        self.logger.info(f"Review request saved: {review_path}")
        return review_path

    def run_daily_check(self, update_originals: bool = False) -> Dict[str, Dict]:
        """Run the daily documentation check."""
        self.logger.info("Starting daily documentation check...")
        
        # Fetch latest information from AI platforms
        latest_info = self.fetch_latest_info()
        
        results = {}
        
        for doc_name in self.config["documents"]:
            doc_path = self.docs_dir / doc_name
            
            if not doc_path.exists():
                self.logger.warning(f"Document not found: {doc_path}")
                continue
            
            self.logger.info(f"Checking {doc_name}...")
            
            # Analyze if changes are needed
            needs_update, analysis = self.analyze_changes(doc_path, latest_info)
            
            results[doc_name] = {
                "needs_update": needs_update,
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }
            
            if needs_update:
                self.logger.info(f"Updates needed for {doc_name}")
                
                # Create updated version
                updated_content = self.create_updated_document(doc_path, latest_info, analysis)
                
                if updated_content:
                    # Save versioned copy
                    version_path = self.save_version(doc_path, updated_content, results[doc_name])
                    results[doc_name]["version_created"] = str(version_path)
                    
                    # Optionally update original
                    if update_originals:
                        self.update_original_document(doc_path, updated_content)
                        results[doc_name]["original_updated"] = True
                    
                    self.logger.info(f"Created updated version: {version_path}")
                else:
                    self.logger.error(f"Failed to create updated content for {doc_name}")
            else:
                self.logger.info(f"No updates needed for {doc_name}")
        
        # Save check results
        run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_path = self.versions_dir / f"check_results_{run_id}.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)

        # Generate a review request file so humans know what to review
        review_path = self.generate_review_request(run_id, results)
        if review_path:
            self.logger.info(
                f"Human review requested. Run: python feedback_collector.py review"
            )

        return results
    
    def generate_change_summary(self, results: Dict[str, Dict]) -> str:
        """Generate a summary of changes detected."""
        summary = f"# Documentation Check Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        updated_docs = [doc for doc, info in results.items() if info.get("needs_update", False)]
        
        if not updated_docs:
            summary += "✅ **No updates needed** - All documentation is current.\n\n"
        else:
            summary += f"🔄 **{len(updated_docs)} documents updated:**\n\n"
            
            for doc in updated_docs:
                info = results[doc]
                summary += f"### {doc}\n"
                summary += f"- **Status:** Updated\n"
                summary += f"- **Version Created:** {info.get('version_created', 'N/A')}\n"
                summary += f"- **Analysis:** {info.get('analysis', 'N/A')[:200]}...\n\n"
        
        # Add unchanged docs
        unchanged_docs = [doc for doc, info in results.items() if not info.get("needs_update", False)]
        if unchanged_docs:
            summary += f"📋 **{len(unchanged_docs)} documents unchanged:**\n"
            for doc in unchanged_docs:
                summary += f"- {doc}\n"
        
        return summary

def main():
    parser = argparse.ArgumentParser(description="AI Documentation Auto-Updater")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--update-originals", action="store_true",
                        help="Update original files (not just create versions)")
    parser.add_argument("--summary-only", action="store_true",
                        help="Generate summary of last check results")
    parser.add_argument("--review", action="store_true",
                        help="Launch interactive human review session for pending doc updates")

    args = parser.parse_args()

    updater = AIDocumentationUpdater(args.config)

    if args.review:
        updater.feedback.interactive_review()
        return

    if args.summary_only:
        # Find latest results file
        results_files = list(updater.versions_dir.glob("check_results_*.json"))
        if results_files:
            latest_results = sorted(results_files)[-1]
            with open(latest_results, 'r') as f:
                results = json.load(f)
            summary = updater.generate_change_summary(results)
            print(summary)
        else:
            print("No previous check results found.")
    else:
        # Run the daily check
        results = updater.run_daily_check(update_originals=args.update_originals)
        summary = updater.generate_change_summary(results)
        print(summary)
        
        # Save summary
        summary_path = updater.versions_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(summary_path, 'w') as f:
            f.write(summary)

if __name__ == "__main__":
    main()
