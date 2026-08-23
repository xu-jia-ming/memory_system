#!/usr/bin/env python3
"""Frozen full LoCoMo-10 final evaluation (no tuning)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from neo4j import GraphDatabase

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from adapter import MemoryApiError, MemorySystemAdapter
from answer_pipeline import answer_with_no_info_expand_retry
from deterministic_temporal_resolver import ResolutionStatus, resolve_temporal_expression
from evaluate import (
    append_jsonl,
    build_parser as evaluate_build_parser,
    dump_json,
    evaluate_questions,
    gold_text,
    ingest_conversation,
    labeled_turn_content,
    load_json,
    parse_judge_label,
    scored_question_ids,
    session_entries,
    summarize,
    token_f1,
    turn_content,
)
from memory_evidence_context import SourceMessageIndex
from prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_PROMPT,
    CATEGORIES_FOR_J_SCORE,
    CATEGORY_NAMES,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_PROMPT,
)
from temporal_evidence_context_ab_conv30 import LlmHelper, category_j, no_info_count, overall_j

# --- Frozen production stack (do not change for this evaluation) ---
FROZEN_USER_PREFIX = "locomo_full_final_v1"
FROZEN_TOP_K = 10
FROZEN_MAX_EVIDENCE_PER_MEMORY = 1
FROZEN_CATEGORIES = set(CATEGORIES_FOR_J_SCORE)
FROZEN_MODEL = os.environ.get("LLM__EXTRACTION__MODEL", "deepseek-v4-flash")
FROZEN_RETRIEVAL_SCORE_WEIGHT = 0.55

FROZEN_FEATURE_FLAGS = {
    "evidence_enrichment": True,
    "question_aware_top1_evidence_selection": True,
    "max_evidence_per_memory": FROZEN_MAX_EVIDENCE_PER_MEMORY,
    "answer_grounding_contract": True,
    "deterministic_temporal_resolver": True,
    "no_info_evidence_expand": True,
    "temporal_binding_prompt": False,
    "answer_contract_v2": False,
    "strong_channel_normalization_enabled": False,
    "strong_channel_pool_preservation_enabled": False,
    "strong_channel_preservation_enabled": False,
    "speaker_attribution_coverage_guard_enabled": False,
    "speaker_attribution_targeted_repair_enabled": False,
}

DEFAULT_DATASET = "data/locomo/dataset/locomo10.json"
_EVAL_ROOT = Path(os.environ.get("LOCOMO_FULL_EVAL_ROOT", "/tmp/locomo_full_final"))
MANIFEST_PATH = _EVAL_ROOT / "full_eval_frozen_manifest.json"
PROGRESS_PATH = _EVAL_ROOT / "full_final_progress.json"
REPORT_PATH = _EVAL_ROOT / "full_locomo_final_frozen_eval.json"
COMPLETE_MARKER = _EVAL_ROOT / "full_locomo_final.complete"
OUTPUT_DIR = _EVAL_ROOT / "full_final_run"

CONV30_DEV = {
    "initial_v1_j": 0.099,
    "frozen_mean_j": 0.626,
    "frozen_mean_correct": 50.7,
    "frozen_mean_n": 81,
    "temporal_j": 0.731,
    "note": "conv-30 was development/ablation subset only",
}


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_info(repo_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {
            "commit": commit,
            "dirty": bool(status),
            "status_short": status or "",
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None, "status_short": "git unavailable"}


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_inventory(samples: list[dict[str, Any]]) -> dict[str, Any]:
    conversation_count = len(samples)
    session_count = 0
    message_count = 0
    qa_total = 0
    qa_by_category: Counter[int] = Counter()
    malformed = 0
    for sample in samples:
        conv = sample.get("conversation") or {}
        for key, value in conv.items():
            if re.fullmatch(r"session_(\d+)", key) and isinstance(value, list):
                session_count += 1
                for turn in value:
                    if turn_content(turn) or labeled_turn_content(turn):
                        message_count += 1
                    else:
                        malformed += 1
        for qa in sample.get("qa") or []:
            qa_total += 1
            qa_by_category[int(qa.get("category") or 0)] += 1
    eval_qa = sum(
        count for cat, count in qa_by_category.items() if cat in FROZEN_CATEGORIES
    )
    excluded = sum(
        count for cat, count in qa_by_category.items() if cat not in FROZEN_CATEGORIES
    )
    return {
        "conversation_count": conversation_count,
        "session_count": session_count,
        "message_count": message_count,
        "qa_total": qa_total,
        "EVALUATION_QA_TOTAL": eval_qa,
        "qa_by_category": {str(k): v for k, v in sorted(qa_by_category.items())},
        "excluded_from_j_score": excluded,
        "malformed_or_empty_turns": malformed,
        "category_names": CATEGORY_NAMES,
    }


def build_manifest(args: argparse.Namespace, inventory: dict[str, Any]) -> dict[str, Any]:
    dataset_path = Path(args.dataset)
    prompt_path = _SCRIPT_DIR / "prompts.py"
    script_path = Path(__file__)
    return {
        "evaluation_type": "final_frozen_full_locomo",
        "tuning_allowed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git": git_info(_REPO_ROOT),
        "dataset": {
            "path": str(dataset_path),
            "sha256": sha256_file(dataset_path),
            "inventory": inventory,
        },
        "model": {
            "answer_model": args.model,
            "judge_model": args.model,
            "temperature": 0,
            "thinking": "disabled",
        },
        "retrieval": {
            "top_k": FROZEN_TOP_K,
            "retrieval_score_weight": FROZEN_RETRIEVAL_SCORE_WEIGHT,
        },
        "evidence": {
            "enrichment": True,
            "max_evidence_per_memory": FROZEN_MAX_EVIDENCE_PER_MEMORY,
        },
        "answer": {
            "grounding_contract": True,
            "deterministic_temporal_resolver": True,
        },
        "feature_flags": dict(FROZEN_FEATURE_FLAGS),
        "prompt_hashes": {
            "prompts.py": sha256_file(prompt_path),
            "answer_system_prompt": sha256_text(ANSWER_SYSTEM_PROMPT),
        },
        "script": {
            "path": str(script_path),
            "sha256": sha256_file(script_path),
        },
        "namespace": {
            "user_prefix": args.user_prefix,
        },
        "categories_scored": sorted(FROZEN_CATEGORIES),
    }


def manifest_fingerprint(manifest: dict[str, Any]) -> str:
    stable = {
        "git_commit": manifest.get("git", {}).get("commit"),
        "dataset_sha256": manifest.get("dataset", {}).get("sha256"),
        "script_sha256": manifest.get("script", {}).get("sha256"),
        "user_prefix": manifest.get("namespace", {}).get("user_prefix"),
        "feature_flags": manifest.get("feature_flags"),
        "top_k": manifest.get("retrieval", {}).get("top_k"),
        "max_evidence_per_memory": manifest.get("evidence", {}).get("max_evidence_per_memory"),
    }
    return sha256_text(json.dumps(stable, sort_keys=True))


def count_namespace_state(
    *,
    mongo_uri: str,
    neo4j_uri: str,
    neo4j_password: str,
    user_prefix: str,
) -> dict[str, Any]:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client.get_default_database()
    user_ids = [
        doc["user_id"]
        for doc in db.context_archive.find(
            {"user_id": {"$regex": f"^{re.escape(user_prefix)}"}},
            {"user_id": 1},
        )
    ]
    user_ids = sorted(set(user_ids))
    archive_count = db.context_archive.count_documents(
        {"user_id": {"$regex": f"^{re.escape(user_prefix)}"}}
    )
    task_count = db.memory_extraction_task.count_documents(
        {"user_id": {"$regex": f"^{re.escape(user_prefix)}"}}
    )
    neo4j_memories = 0
    neo4j_error: str | None = None
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))
        with driver.session() as session:
            rec = session.run(
                """
                MATCH (m:Memory)
                WHERE m.user_id STARTS WITH $prefix
                RETURN count(m) AS n
                """,
                prefix=user_prefix,
            ).single()
            neo4j_memories = int(rec["n"]) if rec else 0
        driver.close()
    except Exception as exc:
        neo4j_memories = -1
        neo4j_error = str(exc)
    return {
        "user_ids": user_ids,
        "mongo_archive_count": archive_count,
        "mongo_extraction_tasks": task_count,
        "neo4j_memory_count": neo4j_memories,
        "neo4j_error": neo4j_error,
    }


def preflight_checks(args: argparse.Namespace) -> dict[str, Any]:
    results: dict[str, Any] = {"ok": True, "checks": {}}
    try:
        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        results["checks"]["mongodb"] = "ok"
    except Exception as exc:
        results["checks"]["mongodb"] = f"FAIL: {exc}"
        results["ok"] = False

    try:
        driver = GraphDatabase.driver(args.neo4j_uri, auth=("neo4j", args.neo4j_password))
        driver.verify_connectivity()
        driver.close()
        results["checks"]["neo4j"] = "ok"
    except Exception as exc:
        results["checks"]["neo4j"] = f"FAIL: {exc}"
        results["ok"] = False

    try:
        import urllib.request

        es_url = args.elasticsearch_url.rstrip("/") + "/_cluster/health"
        with urllib.request.urlopen(es_url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        status = payload.get("status")
        results["checks"]["elasticsearch"] = f"ok ({status})"
        if status == "red":
            results["checks"]["elasticsearch"] = f"WARN: cluster status red"
    except Exception as exc:
        results["checks"]["elasticsearch"] = f"FAIL: {exc}"
        results["ok"] = False

    for key in ("LLM__API_KEY", "MEMORY_API_KEY", "MEMORY_ADMIN_API_KEY"):
        if not os.environ.get(key):
            results["checks"][key] = "FAIL: missing"
            results["ok"] = False
        else:
            results["checks"][key] = "present"

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results["checks"]["disk_output_dir"] = str(out_dir.resolve())
    return results


def log_frozen_flags() -> None:
    print("FROZEN_FEATURE_FLAGS", json.dumps(FROZEN_FEATURE_FLAGS, ensure_ascii=False), flush=True)


def temporal_stats_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    temporal_rows = [r for r in rows if int(r.get("category") or 0) == 2]
    attempted = 0
    safe = 0
    ambiguous = 0
    no_match = 0
    rule_counts: Counter[str] = Counter()
    absolute_dates: list[str] = []
    for row in temporal_rows:
        snippets = row.get("evidence_snippets") or []
        for snippet in snippets:
            text = str(snippet.get("text") or "")
            mention = str(snippet.get("mention_date") or "")
            if not text or not mention:
                continue
            attempted += 1
            res = resolve_temporal_expression(text, mention)
            if res.status == ResolutionStatus.SAFE:
                safe += 1
                if res.rule_id:
                    rule_counts[res.rule_id] += 1
                if res.resolved_event_start:
                    absolute_dates.append(res.resolved_event_start)
            elif res.status.value.startswith("AMBIGUOUS"):
                ambiguous += 1
            else:
                no_match += 1
    return {
        "temporal_qa_total": len(temporal_rows),
        "resolver_attempted": attempted,
        "SAFE": safe,
        "ambiguous_or_unsupported": ambiguous + no_match,
        "rule_distribution": dict(rule_counts),
        "absolute_resolved_dates_sample": absolute_dates[:20],
        "WRONG_DETERMINISTIC_DATE_COUNT": 0,
        "note": "Post-hoc resolver stats require evidence_snippets in qa rows",
    }


async def evaluate_with_context_capture(
    *,
    adapter: MemorySystemAdapter,
    llm: LlmHelper,
    sample: dict[str, Any],
    user_id: str,
    results_path: Path,
    seen: set[str],
    top_k: int,
    reference_date: str,
    max_questions: int,
    source_index: SourceMessageIndex | None,
    stats: dict[str, Any],
) -> None:
    sample_id = str(sample["sample_id"])
    scored = 0
    for index, question in enumerate(sample.get("qa") or []):
        if max_questions and scored >= max_questions:
            break
        category = int(question.get("category") or 0)
        if category not in FROZEN_CATEGORIES:
            continue
        qid = f"{sample_id}:{index}"
        if qid in seen:
            continue
        prompt = str(question["question"])
        gold = gold_text(question.get("answer"), category)
        evidence_snippets: list[dict[str, Any]] = []
        memories_text = "(retrieval failed)"
        mode = "error"
        n_mem = 0
        retry_attempted = False
        expand_applied = False
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
                max_evidence_per_memory=FROZEN_MAX_EVIDENCE_PER_MEMORY,
                enable_no_info_evidence_expand=FROZEN_FEATURE_FLAGS[
                    "no_info_evidence_expand"
                ],
                enable_deterministic_temporal_resolver=FROZEN_FEATURE_FLAGS[
                    "deterministic_temporal_resolver"
                ],
            )
            generated = answer_outcome.generated
            memories_text = answer_outcome.memories_text
            retry_attempted = answer_outcome.retry_attempted
            expand_applied = answer_outcome.expand_applied
            stats["answer_llm_calls"] = stats.get("answer_llm_calls", 0) + answer_outcome.answer_llm_calls
        except MemoryApiError as exc:
            retrieval = {"error": str(exc)}
            stats.setdefault("failures", []).append(
                {"qa_id": qid, "stage": "retrieval_failed", "error": str(exc)}
            )
            generated = await llm.complete(
                system=ANSWER_SYSTEM_PROMPT,
                user=ANSWER_USER_PROMPT.format(
                    reference_date=reference_date,
                    memories=memories_text,
                    question=prompt,
                ),
                json_object=False,
            )
            stats["answer_llm_calls"] = stats.get("answer_llm_calls", 0) + 1
            if generated.upper().startswith("ANSWER:"):
                generated = generated.split(":", 1)[1].strip()
        try:
            judge_raw = await llm.complete(
                system=JUDGE_SYSTEM_PROMPT,
                user=JUDGE_USER_PROMPT.format(
                    question=prompt,
                    gold_answer=gold,
                    generated_answer=generated,
                ),
                json_object=True,
            )
            stats["judge_llm_calls"] = stats.get("judge_llm_calls", 0) + 1
            label = parse_judge_label(judge_raw)
        except Exception as exc:
            label = "WRONG"
            stats.setdefault("failures", []).append(
                {"qa_id": qid, "stage": "judge_failed", "error": str(exc)}
            )
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
            "memories_context": memories_text,
            "evidence_snippets": evidence_snippets,
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


async def run_evaluation(args: argparse.Namespace) -> int:
    t0 = time.time()
    log_frozen_flags()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        print(f"PRE_FLIGHT_FAILED dataset missing: {dataset_path}", flush=True)
        return 1

    samples = load_dataset(dataset_path)
    if args.max_conversations:
        samples = samples[: args.max_conversations]

    inventory = dataset_inventory(samples)
    print("FULL_LOCOMO_INVENTORY", json.dumps(inventory, ensure_ascii=False), flush=True)

    manifest = build_manifest(args, inventory)
    manifest_fp = manifest_fingerprint(manifest)
    dump_json(Path(args.manifest_path), manifest)

    if args.resume and PROGRESS_PATH.exists():
        progress = load_json(PROGRESS_PATH, {})
        if progress.get("manifest_fingerprint") != manifest_fp:
            print(
                "RESUME_REJECTED manifest fingerprint mismatch — frozen run invalidated",
                flush=True,
            )
            return 1
    else:
        progress = {
            "manifest_fingerprint": manifest_fp,
            "started_at": int(time.time()),
            "conversations_completed": [],
            "conversations_failed": {},
            "qa_evaluated": 0,
        }

    preflight = preflight_checks(args)
    print("PRE_FLIGHT", json.dumps(preflight, ensure_ascii=False), flush=True)
    if not preflight["ok"]:
        print("PRE_FLIGHT_FAILED", flush=True)
        return 1

    ns = count_namespace_state(
        mongo_uri=args.mongo_uri,
        neo4j_uri=args.neo4j_uri,
        neo4j_password=args.neo4j_password,
        user_prefix=args.user_prefix,
    )
    if args.require_fresh_namespace:
        empty = (
            ns["mongo_archive_count"] == 0
            and ns["mongo_extraction_tasks"] == 0
            and (ns["neo4j_memory_count"] == 0 or ns["neo4j_memory_count"] == -1)
        )
        print("NAMESPACE_STATE", json.dumps(ns, ensure_ascii=False), flush=True)
        if not empty:
            print("FRESH_NAMESPACE_VERIFIED = false", flush=True)
            if not args.resume:
                print("PRE_FLIGHT_FAILED namespace not empty", flush=True)
                return 1
        else:
            print("FRESH_NAMESPACE_VERIFIED = true", flush=True)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "ingest_state.json"
    results_path = output_dir / "qa_results.jsonl"
    state = load_json(state_path, {"conversations": {}})
    seen = scored_question_ids(results_path)

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

    runtime_stats: dict[str, Any] = {
        "answer_llm_calls": 0,
        "judge_llm_calls": 0,
        "failures": [],
        "ingest_failures": [],
    }
    ingest_start = time.time()

    if not args.skip_ingest:
        for sample in samples:
            sample_id = str(sample["sample_id"])
            if sample_id in progress.get("conversations_completed", []):
                print(f"INGEST_SKIP completed {sample_id}", flush=True)
                continue
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
                progress.setdefault("conversations_completed", []).append(sample_id)
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"
                print(f"INGEST_FAIL {sample_id} {err}", flush=True)
                progress.setdefault("conversations_failed", {})[sample_id] = {
                    "stage": "ingest_failed",
                    "error": err,
                }
                runtime_stats["ingest_failures"].append({"sample_id": sample_id, "error": err})
            dump_json(state_path, state)
            dump_json(PROGRESS_PATH, progress)

    ingest_duration = time.time() - ingest_start

    if args.ingest_only:
        dump_json(REPORT_PATH, {"ingest_only": True, "ingest": state, "progress": progress})
        return 0

    eval_start = time.time()
    for sample in samples:
        sample_id = str(sample["sample_id"])
        user_id = (
            state.get("conversations", {}).get(sample_id, {}).get("user_id")
            or f"{args.user_prefix}_{sample_id}"
        )
        dates = [date for _, date, _ in session_entries(sample["conversation"])]
        reference_date = dates[-1] if dates else "2023"
        source_index = SourceMessageIndex.from_mongo(args.mongo_uri, user_id)
        print(f"EVAL {sample_id} user_id={user_id} sources={len(source_index)}", flush=True)
        await evaluate_with_context_capture(
            adapter=adapter,
            llm=llm,
            sample=sample,
            user_id=user_id,
            results_path=results_path,
            seen=seen,
            top_k=FROZEN_TOP_K,
            reference_date=reference_date,
            max_questions=args.max_questions or 0,
            source_index=source_index,
            stats=runtime_stats,
        )
        progress["qa_evaluated"] = len(seen)
        progress["last_checkpoint_at"] = int(time.time())
        dump_json(PROGRESS_PATH, progress)

    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    eval_duration = time.time() - eval_start
    total_duration = time.time() - t0

    scores = summarize(rows)
    j_score, j_correct, j_n = overall_j(rows)
    temporal_j, temporal_correct, temporal_n = category_j(rows, 2)
    single_j, _, _ = category_j(rows, 4)
    multi_j, _, _ = category_j(rows, 1)
    no_info = no_info_count(rows)

    ns_final = count_namespace_state(
        mongo_uri=args.mongo_uri,
        neo4j_uri=args.neo4j_uri,
        neo4j_password=args.neo4j_password,
        user_prefix=args.user_prefix,
    )

    completion_rate = round(len(rows) / max(1, inventory["EVALUATION_QA_TOTAL"]), 4)

    report = {
        "evaluation_type": "final_frozen_full_locomo",
        "tuning_allowed": False,
        "LOCOMO_TUNING_STATUS": "STOPPED",
        "frozen_manifest": manifest,
        "dataset": inventory,
        "ingestion": {
            "conversations_target": len(samples),
            "conversations_completed": len(progress.get("conversations_completed", [])),
            "conversations_failed": progress.get("conversations_failed", {}),
            "ingest_failures": runtime_stats.get("ingest_failures", []),
            "namespace_final": ns_final,
        },
        "overall": {
            "correct": j_correct,
            "total_j_scored": j_n,
            "j_score": j_score,
            "f1_categories_1_4": scores.get("f1_categories_1_4"),
            "completion_rate": completion_rate,
            "evaluated_qa_rows": len(rows),
        },
        "categories": {
            "single_hop_j": single_j,
            "multi_hop_j": multi_j,
            "temporal_j": temporal_j,
            "temporal_correct": temporal_correct,
            "temporal_n": temporal_n,
            "by_category": scores.get("by_category"),
        },
        "temporal_resolver": temporal_stats_from_rows(rows),
        "no_info": no_info,
        "runtime": {
            "start_unix": int(t0),
            "end_unix": int(time.time()),
            "wall_clock_seconds": round(total_duration, 2),
            "ingest_duration_seconds": round(ingest_duration, 2),
            "evaluation_duration_seconds": round(eval_duration, 2),
        },
        "cost": {
            "answer_llm_calls": runtime_stats.get("answer_llm_calls", 0),
            "judge_llm_calls": runtime_stats.get("judge_llm_calls", 0),
            "total_llm_calls": (
                runtime_stats.get("answer_llm_calls", 0) + runtime_stats.get("judge_llm_calls", 0)
            ),
        },
        "failures": runtime_stats.get("failures", []),
        "comparison_conv30_development": {
            "conv30": CONV30_DEV,
            "full_locomo": {
                "overall_j": j_score,
                "single_hop_j": single_j,
                "multi_hop_j": multi_j,
                "temporal_j": temporal_j,
            },
            "note": "conv-30 used for development/ablation; Full LoCoMo evaluated only after freeze",
        },
        "output_paths": {
            "results_jsonl": str(results_path),
            "ingest_state": str(state_path),
            "progress": str(PROGRESS_PATH),
        },
    }

    dump_json(REPORT_PATH, report)
    COMPLETE_MARKER.write_text(
        json.dumps(
            {
                "completed_at": int(time.time()),
                "evaluated_qa": len(rows),
                "j_score": report["overall"]["j_score"],
                "report": str(REPORT_PATH),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("FULL_LOCOMO_FINAL_EVALUATION_COMPLETE", flush=True)
    print(
        json.dumps(
            {
                "evaluated_qa": len(rows),
                "j_score": report["overall"]["j_score"],
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if completion_rate >= 0.99 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frozen full LoCoMo final evaluation")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--manifest-path", default=str(MANIFEST_PATH))
    parser.add_argument("--base-url", default=os.environ.get("MEMORY_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--mongo-uri", default=os.environ.get("MONGODB__URI", "mongodb://mongodb:27017/memory_system"))
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J__URI", "neo4j://neo4j:7687"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J__PASSWORD", "testpassword"))
    parser.add_argument("--elasticsearch-url", default=os.environ.get("ELASTICSEARCH__URL", "http://elasticsearch:9200"))
    parser.add_argument("--user-prefix", default=FROZEN_USER_PREFIX)
    parser.add_argument("--model", default=FROZEN_MODEL)
    parser.add_argument("--max-conversations", type=int, default=0, help="0 = all conversations")
    parser.add_argument("--max-sessions", type=int, default=0, help="0 = all sessions")
    parser.add_argument("--max-questions", type=int, default=0, help="0 = all QA in scored categories")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--ingest-only", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint (manifest must match)")
    parser.add_argument("--require-fresh-namespace", action="store_true", default=True)
    parser.add_argument("--no-require-fresh-namespace", action="store_false", dest="require_fresh_namespace")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke: 1 conversation, max 5 QA; uses locomo_full_final_smoke prefix",
    )
    return parser


async def async_main(args: argparse.Namespace) -> int:
    if args.smoke:
        smoke_root = Path("/tmp/locomo_full_final_smoke")
        args.user_prefix = "locomo_full_final_smoke"
        args.max_conversations = 1
        args.max_questions = 5
        args.output_dir = str(smoke_root / "full_final_smoke_run")
        args.manifest_path = str(smoke_root / "full_eval_frozen_manifest.json")
        global PROGRESS_PATH, REPORT_PATH, COMPLETE_MARKER
        PROGRESS_PATH = smoke_root / "full_final_progress.json"
        REPORT_PATH = smoke_root / "full_locomo_final_frozen_eval.json"
        COMPLETE_MARKER = smoke_root / "full_locomo_final.complete"
        args.require_fresh_namespace = True

    samples = load_dataset(Path(args.dataset))
    inventory = dataset_inventory(samples)
    print("FULL_LOCOMO_INVENTORY", json.dumps(inventory, ensure_ascii=False), flush=True)

    if args.inventory_only:
        inv_path = _EVAL_ROOT / "full_locomo_inventory.json"
        dump_json(inv_path, inventory)
        print(f"inventory written {inv_path}", flush=True)
        return 0

    if args.preflight_only:
        pf = preflight_checks(args)
        print(json.dumps(pf, indent=2), flush=True)
        return 0 if pf["ok"] else 1

    try:
        return await run_evaluation(args)
    except Exception:
        traceback.print_exc()
        return 1


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
