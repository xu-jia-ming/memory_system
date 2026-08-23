#!/usr/bin/env python3
"""Ingest LoCoMo-10 into Memory System MVP and score QA with LLM-as-judge."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from adapter import MemoryApiError, MemorySystemAdapter
from answer_pipeline import answer_with_no_info_expand_retry
from memory_evidence_context import SourceMessageIndex
from prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_PROMPT,
    CATEGORIES_FOR_J_SCORE,
    CATEGORY_NAMES,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_PROMPT,
)

_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "is",
    "was",
    "were",
    "be",
}


def parse_locomo_datetime(value: str) -> int:
    text = value.strip()
    for fmt in ("%I:%M %p on %d %B, %Y", "%I:%M %p on %d %B %Y"):
        try:
            return int(datetime.strptime(text, fmt).timestamp())
        except ValueError:
            continue
    raise ValueError(f"unrecognized LoCoMo datetime: {value!r}")


def gold_text(answer: Any, category: int) -> str:
    if answer is None:
        return "No information available"
    text = str(answer).strip()
    if not text or text.lower() == "none":
        return "No information available"
    if category == 3 and ";" in text:
        return text.split(";", 1)[0].strip()
    return text


def turn_content(turn: dict[str, Any]) -> str:
    text = str(turn.get("text") or "").strip()
    caption = str(turn.get("blip_caption") or "").strip()
    if caption:
        extra = f"[Image: {caption}]"
        return f"{text} {extra}".strip() if text else extra
    return text


def session_entries(conversation: dict[str, Any]) -> list[tuple[int, str, list[dict[str, Any]]]]:
    entries: list[tuple[int, str, list[dict[str, Any]]]] = []
    for key, value in conversation.items():
        match = re.fullmatch(r"session_(\d+)", key)
        if not match or not isinstance(value, list):
            continue
        index = int(match.group(1))
        dt_key = f"session_{index}_date_time"
        entries.append((index, str(conversation[dt_key]), value))
    entries.sort(key=lambda item: item[0])
    return entries


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


def token_f1(gold: str, predicted: str) -> float:
    gold_tokens = tokenize(gold)
    pred_tokens = tokenize(predicted)
    if not gold_tokens and not pred_tokens:
        return 1.0
    if not gold_tokens or not pred_tokens:
        return 0.0
    overlap = sum((Counter(gold_tokens) & Counter(pred_tokens)).values())
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def scored_question_ids(path: Path) -> set[str]:
    seen: set[str] = set()
    if not path.exists():
        return seen
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        seen.add(str(row["id"]))
    return seen


class LlmHelper:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, *, system: str, user: str, json_object: bool) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 512,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        if json_object:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        return content.strip()


def parse_judge_label(raw: str) -> str:
    try:
        payload = json.loads(raw)
        label = str(payload.get("label") or "").upper()
        if label in {"CORRECT", "WRONG"}:
            return label
    except json.JSONDecodeError:
        pass
    upper = raw.upper()
    if "CORRECT" in upper and "WRONG" not in upper:
        return "CORRECT"
    if "WRONG" in upper and "CORRECT" not in upper:
        return "WRONG"
    return "WRONG"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({int(row["category"]) for row in rows}):
        subset = [row for row in rows if int(row["category"]) == category]
        judged = [row for row in subset if row.get("label") in {"CORRECT", "WRONG"}]
        correct = sum(1 for row in judged if row["label"] == "CORRECT")
        f1_values = [float(row["f1"]) for row in subset if isinstance(row.get("f1"), (int, float))]
        by_category[str(category)] = {
            "name": CATEGORY_NAMES.get(category, str(category)),
            "n": len(subset),
            "llm_score": None if not judged else round(correct / len(judged), 4),
            "f1": None if not f1_values else round(sum(f1_values) / len(f1_values), 4),
        }
    j_rows = [row for row in rows if int(row["category"]) in CATEGORIES_FOR_J_SCORE]
    j_judged = [row for row in j_rows if row.get("label") in {"CORRECT", "WRONG"}]
    j_correct = sum(1 for row in j_judged if row["label"] == "CORRECT")
    j_f1 = [float(row["f1"]) for row in j_rows if isinstance(row.get("f1"), (int, float))]
    return {
        "n_scored": len(rows),
        "j_score_categories_1_4": None if not j_judged else round(j_correct / len(j_judged), 4),
        "j_n": len(j_judged),
        "f1_categories_1_4": None if not j_f1 else round(sum(j_f1) / len(j_f1), 4),
        "by_category": by_category,
    }


def labeled_turn_content(turn: dict[str, Any]) -> str:
    body = turn_content(turn)
    speaker = str(turn.get("speaker") or "").strip()
    if not body:
        return ""
    if speaker:
        return f"[{speaker}] {body}"
    return body


def ingest_conversation(
    adapter: MemorySystemAdapter,
    sample: dict[str, Any],
    *,
    state: dict[str, Any],
    state_path: Path,
    user_prefix: str,
    max_sessions: int | None,
) -> dict[str, Any]:
    sample_id = str(sample["sample_id"])
    user_id = f"{user_prefix}_{sample_id}"
    conversation = sample["conversation"]
    record = state.setdefault("conversations", {}).setdefault(
        sample_id,
        {"user_id": user_id, "sessions": {}},
    )
    record["user_id"] = user_id
    sessions = record["sessions"]
    entries = session_entries(conversation)
    if max_sessions is not None:
        entries = entries[:max_sessions]
    for index, date_text, turns in entries:
        key = str(index)
        existing = sessions.get(key)
        if isinstance(existing, dict) and existing.get("extraction_status") == "completed":
            print(f"  skip ingested {sample_id} session_{index}", flush=True)
            continue
        base_ts = parse_locomo_datetime(date_text)
        session_id = adapter.create_session(user_id)
        written = 0
        for offset, turn in enumerate(turns):
            content = labeled_turn_content(turn)
            if not content:
                continue
            adapter.write_message(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=content,
                timestamp=base_ts + offset,
            )
            written += 1
        archive_ids = adapter.close_session(user_id, session_id) if written else []
        failed = []
        archive_statuses: list[str] = []
        for archive_id in archive_ids:
            result = adapter.wait_for_extraction(user_id, archive_id)
            status = str(result.get("status") or "unknown")
            archive_statuses.append(status)
            if status != "completed":
                failed.append(
                    {
                        "archive_id": archive_id,
                        "status": status,
                        "last_error": result.get("last_error"),
                    }
                )
        if not archive_ids:
            extraction_status = "no_archive"
        elif archive_statuses and all(item == "completed" for item in archive_statuses):
            extraction_status = "completed"
        else:
            extraction_status = "failed"
        sessions[key] = {
            "session_id": session_id,
            "archive_ids": archive_ids,
            "written": written,
            "datetime": date_text,
            "extraction_status": extraction_status,
            "failed": failed,
        }
        dump_json(state_path, state)
        print(
            f"  ingested {sample_id} session_{index} turns={written} "
            f"archives={len(archive_ids)} extraction={extraction_status}",
            flush=True,
        )
    completed = sum(1 for item in sessions.values() if item.get("extraction_status") == "completed")
    record["completed_sessions"] = completed
    record["total_sessions"] = len(sessions)
    return record


async def evaluate_questions(
    *,
    adapter: MemorySystemAdapter,
    llm: LlmHelper,
    sample: dict[str, Any],
    user_id: str,
    results_path: Path,
    seen: set[str],
    categories: set[int],
    top_k: int,
    reference_date: str,
    max_questions: int,
    source_index: SourceMessageIndex | None = None,
    max_evidence_per_memory: int | None = None,
    enable_no_info_evidence_expand: bool = True,
    enable_deterministic_temporal_resolver: bool = True,
) -> None:
    sample_id = str(sample["sample_id"])
    scored = 0
    for index, question in enumerate(sample.get("qa") or []):
        if max_questions and scored >= max_questions:
            break
        category = int(question.get("category") or 0)
        if category not in categories:
            continue
        qid = f"{sample_id}:{index}"
        if qid in seen:
            continue
        prompt = str(question["question"])
        gold = gold_text(question.get("answer"), category)
        try:
            retrieval = adapter.retrieve(user_id=user_id, query=prompt, top_k=top_k)
            mode = retrieval.get("retrieval_mode")
            n_mem = len(retrieval.get("memories") or [])
            answer_outcome = await answer_with_no_info_expand_retry(
                llm,
                system_prompt=ANSWER_SYSTEM_PROMPT,
                question=prompt,
                reference_date=reference_date,
                retrieval=retrieval,
                source_index=source_index,
                max_evidence_per_memory=max_evidence_per_memory,
                enable_no_info_evidence_expand=enable_no_info_evidence_expand,
                enable_deterministic_temporal_resolver=enable_deterministic_temporal_resolver,
            )
            generated = answer_outcome.generated
            memories_text = answer_outcome.memories_text
        except MemoryApiError as exc:
            retrieval = {"error": str(exc)}
            memories_text = "(retrieval failed)"
            mode = "error"
            n_mem = 0
            generated = await llm.complete(
                system=ANSWER_SYSTEM_PROMPT,
                user=ANSWER_USER_PROMPT.format(
                    reference_date=reference_date,
                    memories=memories_text,
                    question=prompt,
                ),
                json_object=False,
            )
            if generated.upper().startswith("ANSWER:"):
                generated = generated.split(":", 1)[1].strip()
            answer_outcome = None
        if answer_outcome is None:
            retry_attempted = False
            expand_applied = False
        else:
            retry_attempted = answer_outcome.retry_attempted
            expand_applied = answer_outcome.expand_applied
        judge_raw = await llm.complete(
            system=JUDGE_SYSTEM_PROMPT,
            user=JUDGE_USER_PROMPT.format(
                question=prompt,
                gold_answer=gold,
                generated_answer=generated,
            ),
            json_object=True,
        )
        label = parse_judge_label(judge_raw)
        row = {
            "id": qid,
            "sample_id": sample_id,
            "category": category,
            "category_name": CATEGORY_NAMES.get(category),
            "question": prompt,
            "gold": gold,
            "generated": generated,
            "label": label,
            "f1": round(token_f1(gold, generated), 4),
            "retrieval_mode": mode,
            "n_memories": n_mem,
            "retry_attempted": retry_attempted,
            "expand_applied": expand_applied,
        }
        append_jsonl(results_path, row)
        seen.add(qid)
        scored += 1
        print(
            f"  qa {qid} cat={category} label={label} f1={row['f1']} n_mem={n_mem} mode={mode}",
            flush=True,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LoCoMo eval against Memory System MVP")
    parser.add_argument("--dataset", default="/tmp/locomo10.json")
    parser.add_argument("--output-dir", default="/tmp/locomo_results")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--max-conversations", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--ingest-only", action="store_true")
    parser.add_argument("--max-sessions", type=int, default=0, help="0 means all sessions")
    parser.add_argument("--user-prefix", default="locomo_v2")
    parser.add_argument("--categories", default="1,2,3,4")
    parser.add_argument(
        "--max-questions",
        type=int,
        default=0,
        help="0 means all questions in selected categories",
    )
    parser.add_argument("--model", default=os.environ.get("LLM__EXTRACTION__MODEL", "deepseek-v4-flash"))
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("MONGODB__URI", ""),
        help="When set, enrich Answer context with source message text + date",
    )
    parser.add_argument(
        "--max-evidence-per-memory",
        type=int,
        default=None,
        help="Per-memory Top-N evidence selection (None = ALL)",
    )
    parser.add_argument(
        "--disable-no-info-evidence-expand",
        action="store_true",
        help="Disable single NO_INFO evidence expand retry",
    )
    parser.add_argument(
        "--disable-temporal-resolver",
        action="store_true",
        help="Disable deterministic temporal resolver metadata in evidence",
    )
    return parser


async def async_main(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = json.loads(dataset_path.read_text(encoding="utf-8"))
    samples = samples[: args.max_conversations]
    categories = {int(part) for part in args.categories.split(",") if part.strip()}
    adapter = MemorySystemAdapter(
        base_url=args.base_url,
        api_key=os.environ["MEMORY_API_KEY"],
        admin_key=os.environ["MEMORY_ADMIN_API_KEY"],
    )
    llm = LlmHelper(
        api_key=os.environ["LLM__API_KEY"],
        base_url=os.environ.get("LLM__BASE_URL", "https://api.deepseek.com"),
        model=args.model,
    )
    state_path = output_dir / "ingest_state.json"
    results_path = output_dir / "qa_results.jsonl"
    summary_path = output_dir / "summary.json"
    state = load_json(state_path, {"conversations": {}})
    seen = scored_question_ids(results_path)

    if not args.skip_ingest:
        for sample in samples:
            sample_id = sample["sample_id"]
            print(f"INGEST {sample_id}", flush=True)
            try:
                ingest_conversation(
                    adapter,
                    sample,
                    state=state,
                    state_path=state_path,
                    user_prefix=args.user_prefix,
                    max_sessions=args.max_sessions or None,
                )
            except Exception as exc:
                print(f"INGEST_FAIL {sample_id} {type(exc).__name__}: {exc}", flush=True)
            dump_json(state_path, state)

    if args.ingest_only:
        completed = 0
        failed = 0
        for rec in (state.get("conversations") or {}).values():
            for item in (rec.get("sessions") or {}).values():
                if item.get("extraction_status") == "completed":
                    completed += 1
                else:
                    failed += 1
        print(
            json.dumps({"ingest_only": True, "completed": completed, "failed": failed}, ensure_ascii=False),
            flush=True,
        )
        dump_json(summary_path, {"ingest": state, "updated_unix": int(time.time())})
        return 0

    for sample in samples:
        sample_id = str(sample["sample_id"])
        user_id = (
            state.get("conversations", {}).get(sample_id, {}).get("user_id")
            or f"{args.user_prefix}_{sample_id}"
        )
        dates = [date for _, date, _ in session_entries(sample["conversation"])]
        reference_date = dates[-1] if dates else "2023"
        source_index: SourceMessageIndex | None = None
        if args.mongo_docker_container:
            source_index = SourceMessageIndex.from_docker_mongosh(
                container=args.mongo_docker_container,
                user_id=user_id,
            )
            print(f"  source messages loaded: {len(source_index)}", flush=True)
        elif args.mongo_uri:
            source_index = SourceMessageIndex.from_mongo(args.mongo_uri, user_id)
            print(f"  source messages loaded: {len(source_index)}", flush=True)

        print(f"EVAL {sample_id} user_id={user_id}", flush=True)
        await evaluate_questions(
            adapter=adapter,
            llm=llm,
            sample=sample,
            user_id=user_id,
            results_path=results_path,
            seen=seen,
            categories=categories,
            top_k=args.top_k,
            reference_date=reference_date,
            max_questions=args.max_questions,
            source_index=source_index,
            max_evidence_per_memory=args.max_evidence_per_memory,
            enable_no_info_evidence_expand=not args.disable_no_info_evidence_expand,
            enable_deterministic_temporal_resolver=not args.disable_temporal_resolver,
        )
        rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        summary = {
            "protocol": {
                "dataset": "locomo10.json",
                "j_score": "LLM-as-judge CORRECT/WRONG on categories 1-4",
                "category_names": CATEGORY_NAMES,
                "retriever": "POST /api/v1/memory/retrieval",
                "top_k": args.top_k,
                "answer_model": args.model,
                "judge_model": args.model,
                "rerank": False,
            },
            "ingest": state,
            "scores": summarize(rows),
            "updated_unix": int(time.time()),
        }
        dump_json(summary_path, summary)
        print("SUMMARY", json.dumps(summary["scores"], ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
