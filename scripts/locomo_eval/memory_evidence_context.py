"""Answer-context enrichment: source messages + question-aware evidence selection."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from deterministic_temporal_resolver import (
    TemporalResolutionTelemetry,
    resolve_temporal_expression,
)

_SPEAKER_PREFIX_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)
MAX_SUPPORTING_EVIDENCE_PER_MEMORY = 20

# Mention/source time for enriched evidence (not inferred event occurrence date).
EVIDENCE_DATE_LABEL_LEGACY = "Date"
EVIDENCE_DATE_LABEL_MENTION = "Mentioned on"
DEFAULT_EVIDENCE_DATE_LABEL = EVIDENCE_DATE_LABEL_LEGACY

_RELATIVE_EXPR_RE = re.compile(
    r"\b("
    r"today|yesterday|tomorrow|"
    r"last week|next week|this week|"
    r"last month|next month|this month|"
    r"last year|next year|this year|"
    r"\d+\s+days?\s+ago|\d+\s+weeks?\s+ago|\d+\s+months?\s+ago"
    r")\b",
    re.IGNORECASE,
)

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
        "at", "by", "is", "was", "were", "be", "it", "its", "he", "she", "they",
        "his", "her", "their", "what", "when", "where", "who", "how", "did", "does",
        "has", "have", "had", "are", "do", "that", "this", "which",
    }
)

# Deterministic scoring weights (no grid search).
_W_QUESTION = 1.0
_W_MEMORY = 1.5
_W_ENTITY = 0.5
_W_TEMPORAL_ANCHOR = 3.0


@dataclass(frozen=True, slots=True)
class SourceMessageRecord:
    message_id: str
    content: str
    timestamp: int
    role: str


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    memory_id: str
    source_message_id: str
    text: str
    speaker: str | None
    source_time: int
    original_index: int


@dataclass(frozen=True, slots=True)
class ScoredEvidence:
    candidate: EvidenceCandidate
    score: float
    question_relevance: float
    memory_consistency: float
    entity_match: float
    temporal_anchor_bonus: float


class SourceMessageIndex:
    """User-scoped lookup of archived source messages by message_id."""

    def __init__(self, records: Mapping[str, SourceMessageRecord], user_id: str) -> None:
        self._records = dict(records)
        self.user_id = user_id

    def get(self, message_id: str) -> SourceMessageRecord | None:
        return self._records.get(message_id)

    def __len__(self) -> int:
        return len(self._records)

    @classmethod
    def from_mongo(cls, mongo_uri: str, user_id: str) -> SourceMessageIndex:
        from pymongo import MongoClient

        client = MongoClient(mongo_uri)
        db = client.get_default_database()
        if db is None:
            raise RuntimeError("MongoDB URI must include a default database path")
        records: dict[str, SourceMessageRecord] = {}
        for archive in db.context_archive.find({"user_id": user_id}):
            for raw in archive.get("messages") or []:
                if not isinstance(raw, dict):
                    continue
                message_id = str(raw.get("message_id") or "")
                if not message_id or message_id in records:
                    continue
                records[message_id] = SourceMessageRecord(
                    message_id=message_id,
                    content=str(raw.get("content") or ""),
                    timestamp=int(raw.get("timestamp") or 0),
                    role=str(raw.get("role") or ""),
                )
        return cls(records, user_id)

    @classmethod
    def from_docker_mongosh(
        cls,
        *,
        container: str,
        user_id: str,
        database: str = "memory_system",
    ) -> SourceMessageIndex:
        js = (
            f"const out={{}};"
            f"db.context_archive.find({{user_id:'{user_id}'}}).forEach(a=>{{"
            "a.messages.forEach(m=>{if(!out[m.message_id])out[m.message_id]=m});"
            "});"
            "print(JSON.stringify(out));"
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "mongosh",
                "--quiet",
                database,
                "--eval",
                js,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout.strip())
        records: dict[str, SourceMessageRecord] = {}
        for message_id, raw in payload.items():
            if not isinstance(raw, dict):
                continue
            records[str(message_id)] = SourceMessageRecord(
                message_id=str(message_id),
                content=str(raw.get("content") or ""),
                timestamp=int(raw.get("timestamp") or 0),
                role=str(raw.get("role") or ""),
            )
        return cls(records, user_id)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]


def relative_expressions(text: str) -> frozenset[str]:
    return frozenset(m.group(0).lower() for m in _RELATIVE_EXPR_RE.finditer(text))


def question_token_overlap(question: str, evidence_text: str) -> float:
    q_tokens = set(tokenize(question))
    if not q_tokens:
        return 0.0
    e_tokens = set(tokenize(evidence_text))
    return len(q_tokens & e_tokens) / len(q_tokens)


def memory_token_overlap(memory_content: str, evidence_text: str) -> float:
    m_tokens = set(tokenize(memory_content))
    if not m_tokens:
        return 0.0
    e_tokens = set(tokenize(evidence_text))
    return len(m_tokens & e_tokens) / len(m_tokens)


def entity_match_score(question: str, speaker: str | None, evidence_text: str) -> float:
    entities = re.findall(r"\b[A-Z][a-z]+\b", question)
    if not entities:
        return 0.0
    haystack = f"{speaker or ''} {evidence_text}".lower()
    hits = sum(1 for ent in entities if ent.lower() in haystack)
    return min(float(hits), 2.0)


def temporal_anchor_bonus(memory_content: str, evidence_text: str) -> float:
    mem_exprs = relative_expressions(memory_content)
    if not mem_exprs:
        return 0.0
    ev_lower = evidence_text.lower()
    ev_exprs = relative_expressions(evidence_text)
    if mem_exprs & ev_exprs:
        return 1.0
    for expr in mem_exprs:
        if expr in ev_lower:
            return 1.0
    return 0.0


def score_evidence_candidate(
    question: str,
    memory_content: str,
    candidate: EvidenceCandidate,
) -> ScoredEvidence:
    q_rel = question_token_overlap(question, candidate.text)
    m_rel = memory_token_overlap(memory_content, candidate.text)
    ent = entity_match_score(question, candidate.speaker, candidate.text)
    t_bonus = temporal_anchor_bonus(memory_content, candidate.text)
    total = (
        _W_QUESTION * q_rel
        + _W_MEMORY * m_rel
        + _W_ENTITY * ent
        + _W_TEMPORAL_ANCHOR * t_bonus
    )
    return ScoredEvidence(
        candidate=candidate,
        score=total,
        question_relevance=q_rel,
        memory_consistency=m_rel,
        entity_match=ent,
        temporal_anchor_bonus=t_bonus,
    )


def build_evidence_candidates(
    memory_id: str,
    source_message_ids: list[str],
    source_index: SourceMessageIndex,
) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []
    for index, message_id in enumerate(source_message_ids):
        message_id = str(message_id)
        record = source_index.get(message_id)
        if record is None:
            continue
        speaker, text = parse_speaker_and_text(record.content)
        if not text:
            continue
        candidates.append(
            EvidenceCandidate(
                memory_id=memory_id,
                source_message_id=message_id,
                text=text,
                speaker=speaker,
                source_time=record.timestamp,
                original_index=index,
            )
        )
    return candidates


def select_source_message_ids(
    question: str,
    memory_content: str,
    source_message_ids: list[str],
    source_index: SourceMessageIndex,
    max_evidence_per_memory: int | None,
    memory_id: str = "",
) -> list[str]:
    """Per-memory Top-N evidence selection (deterministic, no gold)."""
    ordered_ids = [str(x) for x in source_message_ids]
    if not ordered_ids or source_index is None:
        return ordered_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]

    if max_evidence_per_memory is None:
        return ordered_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]

    candidates = build_evidence_candidates(memory_id, ordered_ids, source_index)
    if not candidates:
        return []
    if len(candidates) <= max_evidence_per_memory:
        return [c.source_message_id for c in candidates]

    scored = [
        score_evidence_candidate(question, memory_content, candidate)
        for candidate in candidates
    ]
    scored.sort(
        key=lambda item: (
            -item.score,
            item.candidate.original_index,
            item.candidate.source_time,
            item.candidate.source_message_id,
        )
    )
    return [
        item.candidate.source_message_id for item in scored[:max_evidence_per_memory]
    ]


def diagnose_evidence_selection(
    question: str,
    memory_id: str,
    memory_content: str,
    source_message_ids: list[str],
    source_index: SourceMessageIndex,
    max_evidence_per_memory: int | None,
) -> dict[str, Any]:
    candidates = build_evidence_candidates(memory_id, source_message_ids, source_index)
    scored = [
        score_evidence_candidate(question, memory_content, candidate)
        for candidate in candidates
    ]
    selected = select_source_message_ids(
        question,
        memory_content,
        source_message_ids,
        source_index,
        max_evidence_per_memory,
        memory_id=memory_id,
    )
    return {
        "memory_id": memory_id,
        "memory_content": memory_content,
        "before_ids": [str(x) for x in source_message_ids],
        "scored": [
            {
                "source_message_id": item.candidate.source_message_id,
                "date": format_source_date(item.candidate.source_time),
                "speaker": item.candidate.speaker,
                "text": item.candidate.text[:120],
                "score": round(item.score, 4),
                "question_relevance": round(item.question_relevance, 4),
                "memory_consistency": round(item.memory_consistency, 4),
                "entity_match": round(item.entity_match, 4),
                "temporal_anchor_bonus": round(item.temporal_anchor_bonus, 4),
                "original_index": item.candidate.original_index,
            }
            for item in sorted(
                scored,
                key=lambda x: (
                    -x.score,
                    x.candidate.original_index,
                    x.candidate.source_time,
                    x.candidate.source_message_id,
                ),
            )
        ],
        "selected_ids": selected,
        "max_evidence_per_memory": max_evidence_per_memory,
    }


def parse_speaker_and_text(content: str) -> tuple[str | None, str]:
    text = content.strip()
    match = _SPEAKER_PREFIX_RE.match(text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, text


def format_source_date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def _legacy_memory_line(index: int, memory_type: str | None, content: str) -> str:
    return f"{index}. [{memory_type}] {content}"


def _format_supporting_evidence(
    source_message_ids: list[str],
    source_index: SourceMessageIndex | None,
    evidence_date_label: str = DEFAULT_EVIDENCE_DATE_LABEL,
    enable_deterministic_temporal_resolver: bool = False,
    telemetry: TemporalResolutionTelemetry | None = None,
) -> list[str]:
    if not source_message_ids:
        return []
    lines: list[str] = []
    for message_id in source_message_ids:
        message_id = str(message_id)
        if source_index is None:
            continue
        record = source_index.get(message_id)
        if record is None:
            continue
        speaker, text = parse_speaker_and_text(record.content)
        if not text:
            continue
        block = [f"- {evidence_date_label}: {format_source_date(record.timestamp)}"]
        if speaker:
            block.append(f"  Speaker: {speaker}")
        block.append(f"  Text: {text}")
        if enable_deterministic_temporal_resolver:
            resolution = resolve_temporal_expression(text, record.timestamp)
            if telemetry is not None:
                telemetry.record(resolution)
            block.extend(resolution.to_metadata_lines())
        lines.extend(block)
    return lines


def enriched_evidence_blocks(
    memory: dict[str, Any],
    source_index: SourceMessageIndex | None,
    question: str | None = None,
    max_evidence_per_memory: int | None = None,
) -> list[dict[str, Any]]:
    """Structured supporting evidence for audit attribution (not Answer serialization)."""
    if source_index is None:
        return []
    content = str(memory.get("content") or "").strip()
    memory_id = str(memory.get("memory_id") or "")
    source_ids = [str(x) for x in (memory.get("source_message_ids") or [])]
    if question and max_evidence_per_memory is not None:
        source_ids = select_source_message_ids(
            question,
            content,
            source_ids,
            source_index,
            max_evidence_per_memory,
            memory_id=memory_id,
        )
    blocks: list[dict[str, Any]] = []
    for message_id in source_ids:
        record = source_index.get(message_id)
        if record is None:
            continue
        speaker, text = parse_speaker_and_text(record.content)
        if not text:
            continue
        blocks.append(
            {
                "source_message_id": message_id,
                "date": format_source_date(record.timestamp),
                "speaker": speaker,
                "text": text,
            }
        )
    return blocks


def format_memories(
    retrieval: dict[str, Any],
    source_index: SourceMessageIndex | None = None,
    question: str | None = None,
    max_evidence_per_memory: int | None = None,
    evidence_date_label: str = DEFAULT_EVIDENCE_DATE_LABEL,
    enable_deterministic_temporal_resolver: bool = False,
    temporal_telemetry: TemporalResolutionTelemetry | None = None,
) -> str:
    """Serialize retrieved memories for the Answer LLM."""
    memories = retrieval.get("memories") or []
    if not memories:
        return "(no memories retrieved)"

    if source_index is None:
        lines: list[str] = []
        for index, item in enumerate(memories, start=1):
            content = str(item.get("content") or "").strip()
            memory_type = item.get("memory_type")
            lines.append(_legacy_memory_line(index, memory_type, content))
        return "\n".join(lines)

    prompt = (question or "").strip()
    blocks: list[str] = []
    for index, item in enumerate(memories, start=1):
        content = str(item.get("content") or "").strip()
        memory_type = str(item.get("memory_type") or "unknown")
        memory_id = str(item.get("memory_id") or "")
        block_lines = [
            f"Memory {index}",
            f"Type: {memory_type}",
            f"Content: {content}",
        ]
        source_ids = [str(x) for x in (item.get("source_message_ids") or [])]
        if max_evidence_per_memory is not None and prompt:
            source_ids = select_source_message_ids(
                prompt,
                content,
                source_ids,
                source_index,
                max_evidence_per_memory,
                memory_id=memory_id,
            )
        elif max_evidence_per_memory is None:
            source_ids = source_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]
        else:
            source_ids = source_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]

        evidence_lines = _format_supporting_evidence(
            source_ids,
            source_index,
            evidence_date_label=evidence_date_label,
            enable_deterministic_temporal_resolver=enable_deterministic_temporal_resolver,
            telemetry=temporal_telemetry,
        )
        if evidence_lines:
            block_lines.append("")
            block_lines.append("Supporting evidence:")
            block_lines.extend(evidence_lines)
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def collect_shown_source_message_ids(
    retrieval: dict[str, Any],
    *,
    question: str,
    source_index: SourceMessageIndex | None,
    max_evidence_per_memory: int | None,
) -> set[str]:
    shown: set[str] = set()
    if source_index is None:
        return shown
    prompt = (question or "").strip()
    for item in retrieval.get("memories") or []:
        content = str(item.get("content") or "").strip()
        memory_id = str(item.get("memory_id") or "")
        source_ids = [str(x) for x in (item.get("source_message_ids") or [])]
        if max_evidence_per_memory is not None and prompt:
            selected = select_source_message_ids(
                prompt,
                content,
                source_ids,
                source_index,
                max_evidence_per_memory,
                memory_id=memory_id,
            )
        elif max_evidence_per_memory is None:
            selected = source_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]
        else:
            selected = source_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]
        shown.update(selected)
    return shown


def expandable_source_message_ids(
    retrieval: dict[str, Any],
    shown_ids: set[str],
) -> list[str]:
    expandable: list[str] = []
    seen: set[str] = set()
    for item in retrieval.get("memories") or []:
        for raw_id in item.get("source_message_ids") or []:
            message_id = str(raw_id)
            if message_id in shown_ids or message_id in seen:
                continue
            expandable.append(message_id)
            seen.add(message_id)
    return expandable


def has_expandable_evidence(
    retrieval: dict[str, Any],
    shown_ids: set[str],
) -> bool:
    return bool(expandable_source_message_ids(retrieval, shown_ids))


def format_additional_evidence(
    source_message_ids: list[str],
    source_index: SourceMessageIndex | None,
    *,
    evidence_date_label: str = DEFAULT_EVIDENCE_DATE_LABEL,
    enable_deterministic_temporal_resolver: bool = False,
    temporal_telemetry: TemporalResolutionTelemetry | None = None,
) -> str:
    """Serialize extra source messages for NO_INFO expand retry (no duplicates)."""
    if not source_message_ids or source_index is None:
        return ""
    lines = _format_supporting_evidence(
        [str(message_id) for message_id in source_message_ids],
        source_index,
        evidence_date_label=evidence_date_label,
        enable_deterministic_temporal_resolver=enable_deterministic_temporal_resolver,
        telemetry=temporal_telemetry,
    )
    if not lines:
        return ""
    return "\n".join(lines)


def append_expanded_evidence_context(
    memories_text: str,
    additional_evidence_text: str,
) -> str:
    if not additional_evidence_text.strip():
        return memories_text
    return (
        f"{memories_text.rstrip()}\n\n"
        "Additional supporting evidence (from original messages):\n"
        f"{additional_evidence_text}"
    )


def count_evidence_messages(
    retrieval: dict[str, Any],
    source_index: SourceMessageIndex,
    question: str,
    max_evidence_per_memory: int | None,
) -> int:
    total = 0
    for item in retrieval.get("memories") or []:
        content = str(item.get("content") or "").strip()
        memory_id = str(item.get("memory_id") or "")
        source_ids = [str(x) for x in (item.get("source_message_ids") or [])]
        if max_evidence_per_memory is not None and question:
            source_ids = select_source_message_ids(
                question,
                content,
                source_ids,
                source_index,
                max_evidence_per_memory,
                memory_id=memory_id,
            )
        else:
            source_ids = source_ids[:MAX_SUPPORTING_EVIDENCE_PER_MEMORY]
        total += len(source_ids)
    return total


def context_char_stats(text: str) -> dict[str, int]:
    return {"chars": len(text), "estimated_tokens": max(1, len(text) // 4)}
