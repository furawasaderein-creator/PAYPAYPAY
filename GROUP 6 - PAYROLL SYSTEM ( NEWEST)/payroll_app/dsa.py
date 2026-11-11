from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def linear_search_records(
    records: Sequence[T],
    query: str,
    searchable_text: Callable[[T], str | Sequence[str]],
) -> list[T]:
    """Return rows whose searchable text contains query, ignoring case."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return list(records)
    matches: list[T] = []
    for record in records:
        fields = searchable_text(record)
        if isinstance(fields, str):
            fields = (fields,)
        if any(normalized_query in field.casefold() for field in fields):
            matches.append(record)
    return matches


def merge_sort_records(
    records: Sequence[T],
    key: Callable[[T], Any],
    *,
    reverse: bool = False,
) -> list[T]:
    """Return a stable merge sort without modifying records."""
    length = len(records)
    if length < 2:
        return list(records)

    source = list(records)
    target = source.copy()
    width = 1
    while width < length:
        for start in range(0, length, width * 2):
            middle = min(start + width, length)
            end = min(start + width * 2, length)
            left, right, output = start, middle, start

            while left < middle and right < end:
                left_key = key(source[left])
                right_key = key(source[right])
                if left_key == right_key or (
                    left_key > right_key if reverse else left_key < right_key
                ):
                    target[output] = source[left]
                    left += 1
                else:
                    target[output] = source[right]
                    right += 1
                output += 1

            while left < middle:
                target[output] = source[left]
                left += 1
                output += 1
            while right < end:
                target[output] = source[right]
                right += 1
                output += 1
        source, target = target, source
        width *= 2
    return source


class ChainedHashMap(Generic[K, V]):
    """A hash table using separate chaining to resolve key collisions."""

    _MAX_LOAD_FACTOR = 0.75

    def __init__(self, initial_capacity: int = 8) -> None:
        if initial_capacity < 1:
            raise ValueError("Hash map capacity must be positive.")
        capacity = 1
        while capacity < initial_capacity:
            capacity *= 2
        self._buckets: list[list[tuple[K, V]]] = [
            [] for _ in range(capacity)
        ]
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def __setitem__(self, key: K, value: V) -> None:
        bucket = self._buckets[self._bucket_index(key)]
        for index, (existing_key, _) in enumerate(bucket):
            if existing_key == key:
                bucket[index] = (key, value)
                return

        bucket.append((key, value))
        self._size += 1
        if self._size / len(self._buckets) > self._MAX_LOAD_FACTOR:
            self._resize()

    def __getitem__(self, key: K) -> V:
        bucket = self._buckets[self._bucket_index(key)]
        for existing_key, value in bucket:
            if existing_key == key:
                return value
        raise KeyError(key)

    def get(self, key: K, default: V | None = None) -> V | None:
        try:
            return self[key]
        except KeyError:
            return default

    def _bucket_index(self, key: K) -> int:
        return hash(key) % len(self._buckets)

    def _resize(self) -> None:
        entries = [entry for bucket in self._buckets for entry in bucket]
        self._buckets = [[] for _ in range(len(self._buckets) * 2)]
        for key, value in entries:
            self._buckets[self._bucket_index(key)].append((key, value))
