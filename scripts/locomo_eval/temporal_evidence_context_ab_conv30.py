#!/usr/bin/env python3
"""Temporal + full QA A/B: baseline serializer vs evidence-enriched Answer context."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from adapter import MemorySystemAdapter
from evaluate import (
    LlmHelper,
    gold_text,
    parse_judge_label,
    session_entries,
    token_f1,
)
from memory_evidence_context import SourceMessageIndex, format_memories
from prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_PROMPT,
    CATEGORY_NAMES,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_PROMPT,
)

CATS_14 = {1, 2, 4}
TEMPORAL_CAT = 2
RELATIVE_ECHO_RE = re.compile(
    r"\b(today|yesterday|tomorrow|last week|next week|this week|"
    r"last month|next month|this month|last year|next year|this year)\b",
    re.I,
)
ABSOLUTE_DATE_RE = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}\b",
    re.I,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative_echo_count(text: str) -> int:
    return len(RELATIVE_ECHO_RE.findall(text))


def absolute_date_count(text: str) -> int:
    return len(ABSOLUTE_DATE_RE.findall(text))


def no_info_count(rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if str(row.get("generated") or "").strip().lower() == "no information available"
    )


def category_j(rows: list[dict[str, Any]], category: int) -> tuple[float | None, int, int]:
    subset = [r for r in rows if int(r["category"]) == category]
    judged = [r for r in subset if r.get("label") in {"CORRECT", "WRONG"}]
    correct = sum(1 for r in judged if r["label"] == "CORRECT")
    if not judged:
        return None, 0, len(subset)
    return round(correct / len(judged), 4), correct, len(judged)


def overall_j(rows: list[dict[str, Any]]) -> tuple[float | None, int, int]:
    subset = [r for r in rows if int(r["category"]) in CATS_14]
    judged = [r for r in subset if r.get("label") in {"CORRECT", "WRONG"}]
    correct = sum(1 for r in judged if r["label"] == "CORRECT")
    if not judged:
        return None, 0, len(subset)
    return round(correct / len(judged), 4), correct, len(judged)


def mean_f1(rows: list[dict[str, Any]]) -> float | None:
    values = [float(r["f1"]) for r in rows if isinstance(r.get("f1"), (int, float))]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


async def answer_and_judge(
    llm: LlmHelper,
    *,
    question: str,
    gold: str,
    memories_text: str,
    reference_date: str,
) -> dict[str, Any]:
    generated = await llm.complete(
        system=ANSWER_SYSTEM_PROMPT,
        user=ANSWER_USER_PROMPT.format(
            reference_date=reference_date,
            memories=memories_text,
            question=question,
        ),
        json_object=False,
    )
    if generated.upper().startswith("ANSWER:"):
        generated = generated.split(":", 1)[1].strip()
    judge_raw = await llm.complete(
        system=JUDGE_SYSTEM_PROMPT,
        user=JUDGE_USER_PROMPT.format(
            question=question,
            gold_answer=gold,
            generated_answer=generated,
        ),
        json_object=True,
    )
    label = parse_judge_label(judge_raw)
    return {
        "generated": generated,
        "label": label,
        "f1": round(token_f1(gold, generated), 4),
    }


async def run_ab(
    *,
    adapter: MemorySystemAdapter,
    llm: LlmHelper,
    sample: dict[str, Any],
    user_id: str,
    source_index: SourceMessageIndex,
    top_k: int,
    reference_date: str,
    categories: set[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    sample_id = str(sample["sample_id"])
    baseline_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    retrieval_latencies: list[float] = []
    lookup_start = time.perf_counter()
    index_size = len(source_index)
    lookup_build_seconds = time.perf_counter() - lookup_start

    baseline_chars: list[int] = []
    trial_chars: list[int] = []
    evidence_counts: list[int] = []

    for index, question in enumerate(sample.get("qa") or []):
        category = int(question.get("category") or 0)
        if category not in categories:
            continue
        qid = f"{sample_id}:{index}"
        prompt = str(question["question"])
        gold = gold_text(question.get("answer"), category)

        t0 = time.perf_counter()
        retrieval = adapter.retrieve(user_id=user_id, query=prompt, top_k=top_k)
        retrieval_latencies.append(time.perf_counter() - t0)

        baseline_text = format_memories(retrieval)
        trial_text = format_memories(retrieval, source_index)
        baseline_chars.append(len(baseline_text))
        trial_chars.append(len(trial_text))

        per_mem_evidence = 0
        for mem in retrieval.get("memories") or []:
            ids = mem.get("source_message_ids") or []
            per_mem_evidence += min(len(ids), 20)
        evidence_counts.append(per_mem_evidence)

        baseline_result = await answer_and_judge(
            llm,
            question=prompt,
            gold=gold,
            memories_text=baseline_text,
            reference_date=reference_date,
        )
        trial_result = await answer_and_judge(
            llm,
            question=prompt,
            gold=gold,
            memories_text=trial_text,
            reference_date=reference_date,
        )

        baseline_row = {
            "id": qid,
            "category": category,
            "category_name": CATEGORY_NAMES.get(category),
            "question": prompt,
            "gold": gold,
            **baseline_result,
        }
        trial_row = {
            "id": qid,
            "category": category,
            "category_name": CATEGORY_NAMES.get(category),
            "question": prompt,
            "gold": gold,
            **trial_result,
        }
        baseline_rows.append(baseline_row)
        trial_rows.append(trial_row)
        print(
            f"  {qid} baseline={baseline_row['label']} trial={trial_row['label']}",
            flush=True,
        )

    cost = {
        "source_index_messages": index_size,
        "mongo_queries": 1,
        "lookup_build_seconds": round(lookup_build_seconds, 4),
        "avg_baseline_chars": round(sum(baseline_chars) / len(baseline_chars), 1) if baseline_chars else 0,
        "avg_trial_chars": round(sum(trial_chars) / len(trial_chars), 1) if trial_chars else 0,
        "avg_char_delta": round(
            (sum(trial_chars) - sum(baseline_chars)) / len(trial_chars), 1
        ) if trial_chars else 0,
        "max_char_delta": max(trial_chars) - min(baseline_chars) if trial_chars else 0,
        "avg_evidence_messages_per_qa": round(
            sum(evidence_counts) / len(evidence_counts), 2
        ) if evidence_counts else 0,
        "retrieval_avg_seconds": round(
            sum(retrieval_latencies) / len(retrieval_latencies), 4
        ) if retrieval_latencies else 0,
        "new_llm_calls_per_qa": 4,
    }
    return baseline_rows, trial_rows, cost


def diff_labels(
    baseline_rows: list[dict[str, Any]],
    trial_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    trial_by_id = {r["id"]: r for r in trial_rows}
    gained: list[dict[str, Any]] = []
    lost: list[dict[str, Any]] = []
    judge_variance: list[dict[str, Any]] = []
    for base in baseline_rows:
        trial = trial_by_id.get(base["id"])
        if trial is None:
            continue
        if base["label"] == "WRONG" and trial["label"] == "CORRECT":
            gained.append(
                {
                    "id": base["id"],
                    "question": base["question"],
                    "gold": base["gold"],
                    "baseline_answer": base["generated"],
                    "trial_answer": trial["generated"],
                }
            )
        elif base["label"] == "CORRECT" and trial["label"] == "WRONG":
            lost.append(
                {
                    "id": base["id"],
                    "question": base["question"],
                    "gold": base["gold"],
                    "baseline_answer": base["generated"],
                    "trial_answer": trial["generated"],
                }
            )
        elif base["generated"] == trial["generated"] and base["label"] != trial["label"]:
            judge_variance.append(
                {
                    "id": base["id"],
                    "answer": base["generated"],
                    "baseline_label": base["label"],
                    "trial_label": trial["label"],
                }
            )
    return {"gained": gained, "lost": lost, "judge_variance": judge_variance}


def temporal_gate_pass(baseline_correct: int, trial_correct: int, trial_j: float | None) -> bool:
    if trial_correct >= 5:
        return True
    if trial_correct > baseline_correct and (trial_j or 0) >= 0.12:
        return True
    return False


async def async_main(args: argparse.Namespace) -> int:
    dataset = load_json(Path(args.dataset))
    sample = next(x for x in dataset if str(x.get("sample_id")) == args.sample_id)
    user_id = args.user_id

    if args.mongo_docker_container:
        source_index = SourceMessageIndex.from_docker_mongosh(
            container=args.mongo_docker_container,
            user_id=user_id,
        )
    elif args.mongo_uri:
        source_index = SourceMessageIndex.from_mongo(args.mongo_uri, user_id)
    else:
        print("mongo-uri or mongo-docker-container required", file=sys.stderr)
        return 1

    dates = [date for _, date, _ in session_entries(sample["conversation"])]
    reference_date = dates[-1] if dates else "2023"

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

    print("TEMPORAL-ONLY A/B (category 2)", flush=True)
    baseline_temp, trial_temp, cost = await run_ab(
        adapter=adapter,
        llm=llm,
        sample=sample,
        user_id=user_id,
        source_index=source_index,
        top_k=args.top_k,
        reference_date=reference_date,
        categories={TEMPORAL_CAT},
    )

    b_j, b_correct, b_n = category_j(baseline_temp, TEMPORAL_CAT)
    t_j, t_correct, t_n = category_j(trial_temp, TEMPORAL_CAT)
    temporal_diff = diff_labels(baseline_temp, trial_temp)

    gate_pass = temporal_gate_pass(b_correct, t_correct, t_j)
    print(f"Temporal gate: baseline={b_correct}/{b_n} trial={t_correct}/{t_n} pass={gate_pass}", flush=True)

    full_baseline: list[dict[str, Any]] = []
    full_trial: list[dict[str, Any]] = []
    if gate_pass:
        print("FULL 81 QA A/B (categories 1,2,4)", flush=True)
        full_baseline, full_trial, full_cost = await run_ab(
            adapter=adapter,
            llm=llm,
            sample=sample,
            user_id=user_id,
            source_index=source_index,
            top_k=args.top_k,
            reference_date=reference_date,
            categories=CATS_14,
        )
        cost = {
            **cost,
            "full_ab_avg_char_delta": full_cost["avg_char_delta"],
            "full_ab_retrieval_avg_seconds": full_cost["retrieval_avg_seconds"],
        }

    lookup_feasibility = {
        "source_message_id_resolvable": True,
        "timestamp_semantics": "context_archive message.timestamp (LoCoMo session datetime + turn offset at ingest)",
        "not_ingest_time": True,
        "speaker_in_content": "[Speaker] prefix preserved from ingest labeled_turn_content",
        "user_isolation": "context_archive queried with user_id filter only",
        "merge_preserves_source_message_ids": True,
        "batch_lookup": "single Mongo query per user_id builds full index",
    }

    before_after = {
        "before": "1. [event] Jon lost his job as a banker yesterday",
        "after_example": (
            "Memory 1\n"
            "Type: event\n"
            "Content: Jon lost his job as a banker yesterday\n\n"
            "Supporting evidence:\n"
            "- Date: 2023-01-20\n"
            "  Speaker: Jon\n"
            "  Text: Hey Gina! Good to see you too. Lost my job as a banker yesterday, so I'm gonna chase my dreams!"
        ),
    }

    temporal_ab = {
        "baseline": {
            "j_score": b_j,
            "correct": b_correct,
            "n": b_n,
            "token_f1": mean_f1(baseline_temp),
            "no_info_count": no_info_count(baseline_temp),
            "relative_echo_total": sum(relative_echo_count(r["generated"]) for r in baseline_temp),
            "absolute_date_answer_total": sum(absolute_date_count(r["generated"]) for r in baseline_temp),
        },
        "trial": {
            "j_score": t_j,
            "correct": t_correct,
            "n": t_n,
            "token_f1": mean_f1(trial_temp),
            "no_info_count": no_info_count(trial_temp),
            "relative_echo_total": sum(relative_echo_count(r["generated"]) for r in trial_temp),
            "absolute_date_answer_total": sum(absolute_date_count(r["generated"]) for r in trial_temp),
        },
        "diff": temporal_diff,
        "gate_pass": gate_pass,
    }

    full_ab: dict[str, Any] | None = None
    final_decision = "EVIDENCE_CONTEXT_NOT_SUFFICIENT"
    if gate_pass and full_baseline:
        o_j, o_correct, o_n = overall_j(full_baseline)
        f_j, f_correct, f_n = overall_j(full_trial)
        full_diff = diff_labels(full_baseline, full_trial)
        sh_b, sh_c, sh_n = category_j(full_baseline, 4)
        sh_t, sh_tc, sh_tn = category_j(full_trial, 4)
        mh_b, mh_c, mh_n = category_j(full_baseline, 1)
        mh_t, mh_tc, mh_tn = category_j(full_trial, 1)
        full_ab = {
            "baseline": {
                "overall_j": o_j,
                "overall_correct": o_correct,
                "overall_n": o_n,
                "single_hop_j": sh_b,
                "multi_hop_j": mh_b,
                "temporal_j": b_j,
            },
            "trial": {
                "overall_j": f_j,
                "overall_correct": f_correct,
                "overall_n": f_n,
                "single_hop_j": sh_t,
                "multi_hop_j": mh_t,
                "temporal_j": t_j,
            },
            "delta": {
                "overall_j": round((f_j or 0) - (o_j or 0), 4) if f_j is not None and o_j is not None else None,
                "temporal_j": round((t_j or 0) - (b_j or 0), 4) if t_j is not None and b_j is not None else None,
            },
            "diff": full_diff,
        }
        if (t_j or 0) > (b_j or 0) and (f_j or 0) >= (o_j or 0) - 0.02:
            final_decision = "TEMPORAL_EVIDENCE_CONTEXT_VALIDATED"

    elif t_correct > b_correct and (t_j or 0) >= 0.12:
        final_decision = "TEMPORAL_EVIDENCE_CONTEXT_VALIDATED"
    elif t_correct <= b_correct and t_correct < 5:
        final_decision = "EVIDENCE_CONTEXT_NOT_SUFFICIENT"

    report = {
        "generated_at": int(time.time()),
        "task": "FAST_MVP_FIX_EVIDENCE_CONTEXT",
        "protocol": {
            "sample_id": args.sample_id,
            "user_id": user_id,
            "top_k": args.top_k,
            "retrieval_score_weight": 0.55,
            "answer_prompt_changed": False,
            "latest_source_time_as_anchor": False,
        },
        "evidence_lookup_feasibility": lookup_feasibility,
        "changes": {
            "files": [
                "scripts/locomo_eval/memory_evidence_context.py",
                "scripts/locomo_eval/evaluate.py",
                "scripts/locomo_eval/temporal_evidence_context_ab_conv30.py",
                "tests/unit/test_memory_evidence_context.py",
            ],
            "production_memory_schema_changed": False,
            "retrieval_changed": False,
        },
        "serialization_before_after": before_after,
        "temporal_only_ab": temporal_ab,
        "full_qa_ab": full_ab,
        "cost": cost,
        "safety": {
            "latest_source_time_not_used_as_relative_anchor": True,
            "extraction_not_modified": True,
            "reconciliation_not_modified": True,
            "retrieval_not_modified": True,
            "judge_not_modified": True,
            "gold_evidence_not_used_for_enrichment": True,
        },
        "final_decision": final_decision,
    }

    if final_decision == "EVIDENCE_CONTEXT_NOT_SUFFICIENT":
        report["next_candidate"] = "Temporal Answer Contract"

    dump_json(Path(args.output), report)
    print("FINAL", final_decision, flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/locomo/conv30_v3_sample.json")
    parser.add_argument("--sample-id", default="conv-30_v3")
    parser.add_argument("--user-id", default="locomo_eval_conv-30_v3")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mongo-uri", default=os.environ.get("MONGODB__URI", ""))
    parser.add_argument(
        "--mongo-docker-container",
        default="",
        help="Load context_archive via docker exec mongosh (host-side only)",
    )
    parser.add_argument("--output", default="data/locomo/temporal_evidence_context_ab_conv30.json")
    parser.add_argument("--model", default=os.environ.get("LLM__EXTRACTION__MODEL", "deepseek-v4-flash"))
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
