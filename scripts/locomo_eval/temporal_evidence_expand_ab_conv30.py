#!/usr/bin/env python3
"""4-way ablation: baseline / temporal SAFE_RANGE / NO_INFO expand / combined (conv-30)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from adapter import MemorySystemAdapter
from answer_pipeline import answer_with_no_info_expand_retry
from deterministic_temporal_resolver import TemporalResolutionTelemetry
from evaluate import gold_text, parse_judge_label, session_entries, token_f1
from memory_evidence_context import SourceMessageIndex
from prompts import (
    ANSWER_SYSTEM_PROMPT,
    CATEGORY_NAMES,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_PROMPT,
    is_no_info,
)
from temporal_evidence_context_ab_conv30 import LlmHelper, category_j, no_info_count, overall_j

CATS_14 = {1, 2, 4}
TEMPORAL_CAT = 2
TOP1 = 1
DEFAULT_CACHE = "data/locomo/conv30/caches/deterministic_temporal_resolver_retrieval_cache_conv30.json"
DEFAULT_OUTPUT = "data/locomo/conv30/ablations/temporal_evidence_expand_ab_conv30.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall_j": overall_j(rows),
        "overall_correct": sum(1 for r in rows if r["label"] == "CORRECT"),
        "overall_n": len(rows),
        "temporal_j": category_j(rows, TEMPORAL_CAT),
        "temporal_correct": sum(
            1 for r in rows if int(r["category"]) == TEMPORAL_CAT and r["label"] == "CORRECT"
        ),
        "temporal_n": sum(1 for r in rows if int(r["category"]) == TEMPORAL_CAT),
        "false_no_info_count": no_info_count(rows),
        "retry_attempted": sum(1 for r in rows if r.get("retry_attempted")),
        "expand_applied": sum(1 for r in rows if r.get("expand_applied")),
        "retry_recovered": sum(
            1
            for r in rows
            if r.get("retry_attempted")
            and r["label"] == "CORRECT"
            and is_no_info(r.get("initial_generated", ""))
        ),
    }


async def eval_arm(
    llm: LlmHelper,
    cached: list[dict[str, Any]],
    source_index: SourceMessageIndex,
    *,
    arm_name: str,
    reference_date: str,
    enable_temporal_resolver: bool,
    enable_no_info_expand: bool,
) -> tuple[list[dict[str, Any]], TemporalResolutionTelemetry]:
    telemetry = TemporalResolutionTelemetry()
    rows: list[dict[str, Any]] = []
    for item in cached:
        outcome = await answer_with_no_info_expand_retry(
            llm,
            system_prompt=ANSWER_SYSTEM_PROMPT,
            question=item["question"],
            reference_date=reference_date,
            retrieval=item["retrieval"],
            source_index=source_index,
            max_evidence_per_memory=TOP1,
            enable_no_info_evidence_expand=enable_no_info_expand,
            enable_deterministic_temporal_resolver=enable_temporal_resolver,
            temporal_telemetry=telemetry,
        )
        judge_raw = await llm.complete(
            system=JUDGE_SYSTEM_PROMPT,
            user=JUDGE_USER_PROMPT.format(
                question=item["question"],
                gold_answer=item["gold"],
                generated_answer=outcome.generated,
            ),
            json_object=True,
        )
        label = parse_judge_label(judge_raw)
        rows.append(
            {
                "id": item["id"],
                "category": item["category"],
                "category_name": item.get("category_name"),
                "question": item["question"],
                "gold": item["gold"],
                "generated": outcome.generated,
                "initial_generated": outcome.initial_generated,
                "label": label,
                "f1": round(token_f1(item["gold"], outcome.generated), 4),
                "arm": arm_name,
                "retry_attempted": outcome.retry_attempted,
                "expand_applied": outcome.expand_applied,
                "expanded_message_ids": list(outcome.expanded_message_ids),
                "answer_llm_calls": outcome.answer_llm_calls,
            }
        )
        print(f"  {arm_name} {item['id']} {label}", flush=True)
    return rows, telemetry


async def async_main(args: argparse.Namespace) -> int:
    dataset = load_json(Path(args.dataset))
    sample = next(x for x in dataset if str(x.get("sample_id")) == args.sample_id)
    source_index = SourceMessageIndex.from_mongo(args.mongo_uri, args.user_id)
    dates = [d for _, d, _ in session_entries(sample["conversation"])]
    reference_date = dates[-1] if dates else "2023"

    cache_path = Path(args.retrieval_cache)
    if cache_path.exists() and not args.refresh_cache:
        cached = load_json(cache_path)
        print(f"Loaded retrieval cache n={len(cached)}", flush=True)
    else:
        adapter = MemorySystemAdapter(
            base_url=args.base_url,
            api_key=os.environ["MEMORY_API_KEY"],
            admin_key=os.environ["MEMORY_ADMIN_API_KEY"],
        )
        cached = []
        for index, question in enumerate(sample.get("qa") or []):
            category = int(question.get("category") or 0)
            if category not in CATS_14:
                continue
            qid = f"{args.sample_id}:{index}"
            prompt = str(question["question"])
            retrieval = adapter.retrieve(user_id=args.user_id, query=prompt, top_k=args.top_k)
            cached.append(
                {
                    "id": qid,
                    "category": category,
                    "category_name": CATEGORY_NAMES.get(category),
                    "question": prompt,
                    "gold": gold_text(question.get("answer"), category),
                    "retrieval": retrieval,
                }
            )
        dump_json(cache_path, cached)

    llm = LlmHelper(
        api_key=os.environ["LLM__API_KEY"],
        base_url=os.environ.get("LLM__BASE_URL", "https://api.deepseek.com"),
        model=args.model,
    )

    arms = [
        ("baseline", False, False),
        ("temporal_only", True, False),
        ("expand_only", False, True),
        ("combined", True, True),
    ]
    report: dict[str, Any] = {
        "generated_at": int(time.time()),
        "sample_id": args.sample_id,
        "user_id": args.user_id,
        "arms": {},
    }
    for arm_name, temporal_on, expand_on in arms:
        print(f"ARM {arm_name}", flush=True)
        rows, telemetry = await eval_arm(
            llm,
            cached,
            source_index,
            arm_name=arm_name,
            reference_date=reference_date,
            enable_temporal_resolver=temporal_on,
            enable_no_info_expand=expand_on,
        )
        report["arms"][arm_name] = {
            "flags": {
                "deterministic_temporal_resolver": temporal_on,
                "no_info_evidence_expand": expand_on,
            },
            "metrics": summarize_rows(rows),
            "temporal_telemetry": telemetry.to_dict(),
            "rows": rows,
        }

    dump_json(Path(args.output), report)
    print(json.dumps({k: v["metrics"] for k, v in report["arms"].items()}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Temporal + evidence expand ablation (conv-30)")
    parser.add_argument("--dataset", default="data/locomo/dataset/locomo10.json")
    parser.add_argument("--sample-id", default="conv-30_v3")
    parser.add_argument("--user-id", default="locomo_eval_conv-30_v3")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mongo-uri", default=os.environ.get("MONGODB__URI", ""))
    parser.add_argument("--model", default=os.environ.get("LLM__EXTRACTION__MODEL", "deepseek-v4-flash"))
    parser.add_argument("--retrieval-cache", default=DEFAULT_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh-cache", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(asyncio.run(async_main(build_parser().parse_args())))


if __name__ == "__main__":
    main()
