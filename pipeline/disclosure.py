"""Production-truth disclosures for newly generated podcast audio."""

AI_NARRATION_DISCLOSURE = "Production note: This episode uses AI-generated narration."


def episode_metadata_disclosure(schema_version: int) -> str:
    if schema_version == 2:
        detail = "drafted and independently checked against cited primary-source evidence"
    elif schema_version in {3, 4}:
        detail = "reviewed against its transcript and cited sources"
    else:
        detail = "based on the cited source material"
    return f"Production disclosure: This episode uses AI-generated narration {detail}."
