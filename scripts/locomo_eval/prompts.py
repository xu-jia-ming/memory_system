"""LoCoMo answer and judge prompts (J-score protocol)."""

from __future__ import annotations

CATEGORY_NAMES = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}

CATEGORIES_FOR_J_SCORE = (1, 2, 3, 4)

NO_INFO_PHRASE = "No information available"


def is_no_info(text: str) -> bool:
    return str(text or "").strip().lower() == NO_INFO_PHRASE.lower()


# Phase 2 audit — baseline no-information policy (pre-grounding contract).
CURRENT_NO_INFO_POLICY = {
    "trigger": "If the memories do not contain the answer",
    "exact_phrase": "No information available",
    "checks_memory_content": False,
    "checks_supporting_evidence": False,
    "allows_paraphrase": "unspecified",
    "forbids_inference": "implicit via only use retrieved memories",
    "issues": [
        "Broad trigger 'memories do not contain the answer' without requiring check of Supporting Evidence blocks",
        "No instruction to prefer direct extraction when facts are present",
        "No guidance against refusing when wording differs from the question",
    ],
}

ANSWER_SYSTEM_PROMPT_BASELINE = (
    "You answer questions using only the retrieved long-term memories. "
    "Give a short factual answer. If the memories do not contain the answer, "
    'reply exactly: "No information available".'
)

ANSWER_GROUNDING_CONTRACT = (
    "Grounding rules:\n"
    "1. Before answering, check each Memory's Content and its Supporting Evidence. "
    "If they directly support the answer, use that information.\n"
    "2. Reply \"No information available\" only when the provided memories and "
    "supporting evidence do not contain enough information to answer. Do not refuse "
    "because wording differs from the question, the answer is not an exact copy, "
    "or you are slightly uncertain.\n"
    "3. Do not use outside knowledge, invent facts, guess, or fill in missing information.\n"
    "4. When the answer clearly appears in a Memory or Supporting Evidence, extract "
    "and answer directly."
)

ANSWER_SYSTEM_PROMPT_GROUNDING_ONLY = (
    "You answer questions using only the retrieved long-term memories. "
    "Give a short factual answer. "
    + ANSWER_GROUNDING_CONTRACT
)

ANSWER_CONTRACT_V2 = (
    "Answer contract (extraction and constraints):\n"
    "1. If the requested fact is explicitly stated or clearly paraphrased in a "
    "Memory Content or Supporting Evidence, answer it directly. Do not return "
    "\"No information available\" only because wording differs from the question.\n"
    "2. Identify exactly what the question asks for (who, where, why, which, "
    "first/earliest, last/latest/most recent, before/after, both/all). Answer that "
    "specific request; do not answer a related but different fact.\n"
    "3. If the question asks for multiple items, include all supported requested items "
    "present in the context. Do not add unsupported items.\n"
    "4. If the required fact is genuinely absent from the memories and supporting "
    "evidence, reply exactly: \"No information available\". Do not guess or infer."
)

ANSWER_SYSTEM_PROMPT_V2 = ANSWER_SYSTEM_PROMPT_GROUNDING_ONLY + ANSWER_CONTRACT_V2

ANSWER_SYSTEM_PROMPT = ANSWER_SYSTEM_PROMPT_GROUNDING_ONLY

TEMPORAL_BINDING_CONTRACT = (
    "Temporal binding rules:\n"
    "1. In Supporting evidence, \"Mentioned on\" is when that evidence turn was spoken "
    "(mention/source time). It is not automatically the event occurrence date unless "
    "the text clearly states the event happened on that day.\n"
    "2. If evidence text contains relative time (yesterday, last week, next month, etc.), "
    "interpret it against that evidence's own Mentioned-on date, not other dates or "
    "memory metadata.\n"
    "3. If the question includes a date (on May 23, before/after a date, first/most recent), "
    "decide whether it constrains what was mentioned on that day versus when an event occurred; "
    "do not assume the question date equals the event date.\n"
    "4. For vague relative times (a few years ago, recently, a while ago), do not invent "
    "precise dates; keep the answer at the same granularity as the evidence."
)

ANSWER_USER_PROMPT = """The conversations took place around {reference_date}. Use that period for time questions, not today's date.

Retrieved memories:
{memories}

Question: {question}

Answer:"""

JUDGE_SYSTEM_PROMPT = (
    "You label whether a generated answer is CORRECT or WRONG relative to a gold "
    "answer. Return JSON only."
)

JUDGE_USER_PROMPT = """Your task is to label an answer to a question as CORRECT or WRONG.

You will be given:
(1) a question
(2) a gold (ground truth) answer
(3) a generated answer

Be generous: if the generated answer captures the same fact or topic as the gold
answer, mark CORRECT even if wording, format, or length differ. Dates that refer
to the same day or month count as CORRECT (e.g. "May 7th" vs "7 May 2023").

For gold answers that are "No information available" or empty, mark CORRECT only
if the generated answer also refuses or says the information is not available.

Question: {question}
Gold answer: {gold_answer}
Generated answer: {generated_answer}

Return JSON with keys "label" (CORRECT or WRONG) and "reasoning" (one sentence).
Do not include both CORRECT and WRONG except as the label value.
"""

# --- FAST_MVP diagnostic oracle prompts (evaluation adapter only; not baseline eval) ---

ORACLE_GOLD_EVIDENCE_SYSTEM_PROMPT = (
    "You answer questions using only the gold evidence turns provided below. "
    "Each evidence block includes session date context when available. "
    "Give a short factual answer. If the evidence does not contain the answer, "
    'reply exactly: "No information available".'
)

ORACLE_FULL_CONTEXT_SYSTEM_PROMPT = (
    "You answer questions using only the conversation history provided below. "
    "Do not use outside knowledge. Give a short factual answer. "
    'If the conversation does not contain the answer, reply exactly: "No information available".'
)

TEMPORAL_ANSWER_CONTRACT = (
    "This is a temporal question. If the context includes a session absolute date "
    "and relative expressions (e.g. yesterday, last week, this month) that allow "
    "deriving an absolute date or month, output the absolute date/month matching "
    "the question granularity (day, month, or year as appropriate). "
    "Do not answer with only relative expressions when an absolute date can be derived."
)

ORACLE_GOLD_EVIDENCE_USER_PROMPT = """The conversations took place around {reference_date}. Use that period for time questions, not today's date.

Gold evidence turns:
{memories}

Question: {question}
{temporal_contract}

Answer:"""

ORACLE_FULL_CONTEXT_USER_PROMPT = """The conversations took place around {reference_date}. Use that period for time questions, not today's date.

Conversation history:
{memories}

Question: {question}
{temporal_contract}

Answer:"""
