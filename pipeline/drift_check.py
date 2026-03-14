"""Validate config-to-README drift for generated topic sections."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .render import topic_anchor_markup


DEFAULT_CONFIG = Path("topics/topics.yaml")


def _load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_readme_drift(
    config_path: Path = DEFAULT_CONFIG,
    readme_path: Path = Path("README.md"),
) -> list[str]:
    """Return a list of config-versus-README drift errors."""
    config = _load_config(config_path)
    readme = readme_path.read_text(encoding="utf-8")
    errors: list[str] = []

    last_toc_pos = -1
    last_section_pos = -1

    for topic in config.get("topics", []):
        topic_id = topic["id"]
        display = topic["display"]
        toc_entry = f"- [{display}](#{topic_id})"
        section_block = f"{topic_anchor_markup(topic_id)}\n## {display}"

        toc_pos = readme.find(toc_entry)
        if toc_pos == -1:
            errors.append(f"Missing README topic list entry for '{display}' (#{topic_id}).")
        elif toc_pos < last_toc_pos:
            errors.append(f"README topic list order drifted for '{display}' (#{topic_id}).")
        else:
            last_toc_pos = toc_pos

        section_pos = readme.find(section_block)
        if section_pos == -1:
            anchor_pos = readme.find(topic_anchor_markup(topic_id))
            heading_pos = readme.find(f"## {display}")
            if anchor_pos == -1 and heading_pos == -1:
                errors.append(
                    f"Missing README section and anchor for '{display}' (#{topic_id})."
                )
            elif anchor_pos == -1:
                errors.append(f"Missing explicit README anchor for '{display}' (#{topic_id}).")
            elif heading_pos == -1:
                errors.append(f"Missing README section heading for '{display}' (#{topic_id}).")
            else:
                errors.append(
                    f"README anchor/heading alignment drifted for '{display}' (#{topic_id})."
                )
            continue

        if section_pos < last_section_pos:
            errors.append(f"README topic section order drifted for '{display}' (#{topic_id}).")
        else:
            last_section_pos = section_pos

    return errors


def main() -> int:
    """CLI entry point for config-versus-README drift validation."""
    parser = argparse.ArgumentParser(description="Validate topic config against README")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to topics YAML")
    parser.add_argument("--readme", default="README.md", help="Path to generated README")
    args = parser.parse_args()

    errors = validate_readme_drift(Path(args.config), Path(args.readme))
    if errors:
        for error in errors:
            print(error)
        return 1

    print("README matches configured topics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())