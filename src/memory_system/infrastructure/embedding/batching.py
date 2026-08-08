"""Deterministic First-Fit-In-Order batching for embedding token budgets."""

from __future__ import annotations


def split_into_batches(
    token_counts: list[int],
    *,
    max_batch_size: int,
    max_batch_tokens: int,
) -> list[list[int]]:
    """Group input indices into sub-batches without reordering.

    Each returned batch contains original indices. A new batch starts when adding
    the next item would exceed ``max_batch_size`` or ``max_batch_tokens``.
    """
    if not token_counts:
        return []

    batches: list[list[int]] = []
    current_batch: list[int] = []
    current_token_sum = 0

    for index, token_count in enumerate(token_counts):
        would_exceed_size = len(current_batch) + 1 > max_batch_size
        would_exceed_tokens = current_token_sum + token_count > max_batch_tokens

        if current_batch and (would_exceed_size or would_exceed_tokens):
            batches.append(current_batch)
            current_batch = []
            current_token_sum = 0

        current_batch.append(index)
        current_token_sum += token_count

    if current_batch:
        batches.append(current_batch)

    return batches
