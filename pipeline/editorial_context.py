"""Shared spoken-context requirements; relevance rules are never evidence."""

CONTEXT_INSTRUCTIONS = """
For EVERY included entry, the spoken explanation must stand on its own:
explain what the tool or concept is in plain language on first mention, where it
fits in a larger AI workflow, a concrete use case, why this particular change
matters, and who can skip it or defer action. Experienced audiences still need
orientation to unfamiliar tools; a product name or acronym is not an explanation.
Explain necessary acronyms or avoid them. Connect the tool's input, useful role
and result only to the extent established by supplied primary evidence.
Use a concrete example or helpful analogy, with its limits; never require a
forced analogy. Label hypothetical examples as such. An analogy illustrates a
process, not proof of capability, safety, performance, savings or adoption.
Keep research preview status, availability conditions and evidence limitations
attached to the entry. Explain who can skip conditionally from the supported
workflow; do not invent installed versions, account access or unaffected users.
Global introductions and closing advice cannot substitute for entry-level context.
All factual premises, including background definitions, need primary support.
If essential context is missing, request it in the review handoff or reject/defer
the entry; do not import unsourced knowledge or pad the narration to fill slots.
In the independent audit, reject missing or unsupported context even when each
listed claim has a matching quote. Record an issue and approved=false; do not
repair the draft in the audit. Citation matching alone is not an explanation.
"""
