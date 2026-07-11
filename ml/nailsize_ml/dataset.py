import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True)
class SplitThresholds:
    train: float = 0.70
    validation: float = 0.15

    def __post_init__(self) -> None:
        if not 0 < self.train < 1 or not 0 < self.validation < 1:
            raise ValueError("Split fractions must be between zero and one")
        if self.train + self.validation >= 1:
            raise ValueError("Train and validation fractions must leave a test split")


DEFAULT_THRESHOLDS = SplitThresholds()


def assign_participant_split(
    participant_id: str,
    *,
    salt: str,
    thresholds: SplitThresholds = DEFAULT_THRESHOLDS,
) -> DatasetSplit:
    if not participant_id.strip() or not salt:
        raise ValueError("Participant ID and split salt are required")
    digest = hashlib.sha256(f"{salt}:{participant_id}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    if value < thresholds.train:
        return DatasetSplit.TRAIN
    if value < thresholds.train + thresholds.validation:
        return DatasetSplit.VALIDATION
    return DatasetSplit.TEST


def split_records(
    records: Iterable[Mapping[str, Any]],
    *,
    salt: str,
    thresholds: SplitThresholds = DEFAULT_THRESHOLDS,
) -> dict[DatasetSplit, list[Mapping[str, Any]]]:
    output: dict[DatasetSplit, list[Mapping[str, Any]]] = {split: [] for split in DatasetSplit}
    for record in records:
        participant_id = str(record.get("participant_id", ""))
        split = assign_participant_split(
            participant_id,
            salt=salt,
            thresholds=thresholds,
        )
        output[split].append(record)
    assert_no_participant_leakage(output)
    return output


def assert_no_participant_leakage(
    splits: Mapping[DatasetSplit, Iterable[Mapping[str, Any]]],
) -> None:
    ownership: dict[str, DatasetSplit] = {}
    for split, records in splits.items():
        for record in records:
            participant_id = str(record.get("participant_id", "")).strip()
            if not participant_id:
                raise ValueError("Every record requires a participant_id")
            previous = ownership.setdefault(participant_id, split)
            if previous != split:
                raise ValueError(
                    f"Participant {participant_id!r} appears in {previous} and {split}"
                )
