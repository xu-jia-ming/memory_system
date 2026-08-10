"""Compression LLM prompt templates (§1.2.5)."""

from __future__ import annotations

import json

from memory_system.domain.models.context_archive import ContextArchiveMessage

COMPRESSION_PROMPT_VERSION = "compression_v1"

_SYSTEM_TEMPLATE = """You are a memory compression assistant.

Your task is to merge the previous compressed context with newly archived \
conversation messages and produce a concise context summary for future agent reasoning.

Requirements:

1. Preserve stable user preferences and important user facts.
2. Preserve current user goals and ongoing tasks.
3. Preserve important decisions and their reasons when explicitly stated.
4. Preserve unresolved questions, blockers and pending actions.
5. Preserve necessary conversation state and pending actions.
6. Preserve important temporal order and references.
7. Remove greetings, repeated statements and low-value conversational details.
8. Do not invent, infer or add information that is not present in the input.
9. Do not include hidden reasoning or internal chain-of-thought.
10. Keep the compressed context within the configured estimated-token limit: \
{max_compressed_context_estimated_tokens}.
11. If there is no information worth preserving, return an empty string for compressed_context.
12. Output valid JSON matching the required schema."""

_USER_TEMPLATE = """Previous compressed context:

{compressed_context}


Archived conversation messages:

{messages}


Generate the updated compressed context."""


def serialize_archived_messages(messages: list[ContextArchiveMessage]) -> str:
    """Stable JSON array serialization for prompt ``{messages}`` placeholder."""
    payload = [message.model_dump(mode="json") for message in messages]
    return json.dumps(payload, ensure_ascii=False)


def render_compression_prompts(
    *,
    existing_compressed_context: str,
    archived_messages: list[ContextArchiveMessage],
    max_compressed_context_estimated_tokens: int,
) -> tuple[str, str]:
    """Render system and user prompts for compression LLM."""
    system_prompt = _SYSTEM_TEMPLATE.format(
        max_compressed_context_estimated_tokens=max_compressed_context_estimated_tokens,
    )
    user_prompt = _USER_TEMPLATE.format(
        compressed_context=existing_compressed_context,
        messages=serialize_archived_messages(archived_messages),
    )
    return system_prompt, user_prompt
