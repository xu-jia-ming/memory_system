"""Unit tests for embedding batch splitting."""

from __future__ import annotations

from memory_system.infrastructure.embedding.batching import split_into_batches


def test_split_into_batches_empty() -> None:
    assert split_into_batches([], max_batch_size=64, max_batch_tokens=4096) == []


def test_split_into_batches_single_item() -> None:
    assert split_into_batches([100], max_batch_size=64, max_batch_tokens=4096) == [[0]]


def test_split_into_batches_exact_budget_boundary() -> None:
    token_counts = [1024, 1024, 1024, 1024]
    assert split_into_batches(token_counts, max_batch_size=64, max_batch_tokens=4096) == [
        [0, 1, 2, 3]
    ]


def test_split_into_batches_requires_new_batch_when_budget_exceeded() -> None:
    token_counts = [1024, 1024, 1024, 1024, 1024]
    assert split_into_batches(token_counts, max_batch_size=64, max_batch_tokens=4096) == [
        [0, 1, 2, 3],
        [4],
    ]


def test_split_into_batches_respects_max_batch_size() -> None:
    token_counts = [1] * 65
    assert split_into_batches(token_counts, max_batch_size=64, max_batch_tokens=4096) == [
        list(range(64)),
        [64],
    ]

    token_counts = [1] * 3
    assert split_into_batches(token_counts, max_batch_size=2, max_batch_tokens=4096) == [
        [0, 1],
        [2],
    ]


def test_split_into_batches_first_fit_does_not_reorder() -> None:
    token_counts = [1024, 1024, 1024, 1024, 1024]
    batch_kwargs = {"max_batch_size": 64, "max_batch_tokens": 4096}
    first_order = split_into_batches(token_counts, **batch_kwargs)
    second_order = split_into_batches(token_counts, **batch_kwargs)
    assert first_order == second_order == [[0, 1, 2, 3], [4]]

    reordered_counts = [1024, 1024, 1024, 1024, 1024]
    assert split_into_batches(reordered_counts, max_batch_size=64, max_batch_tokens=4096) == [
        [0, 1, 2, 3],
        [4],
    ]
