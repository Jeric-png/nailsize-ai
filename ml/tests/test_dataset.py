import pytest

from nailsize_ml.dataset import (
    DatasetSplit,
    SplitThresholds,
    assert_no_participant_leakage,
    assign_participant_split,
    split_records,
)


def test_all_records_for_participant_stay_in_one_split() -> None:
    records = [
        {"participant_id": f"participant-{participant}", "image_id": f"{participant}-{image}"}
        for participant in range(100)
        for image in range(6)
    ]
    splits = split_records(records, salt="study-v1-secret")
    ownership: dict[str, DatasetSplit] = {}
    for split, items in splits.items():
        for item in items:
            participant = item["participant_id"]
            assert ownership.setdefault(participant, split) == split
    assert set(ownership) == {f"participant-{value}" for value in range(100)}


def test_split_assignment_is_deterministic_and_salt_specific() -> None:
    first = assign_participant_split("participant-001", salt="salt-a")
    assert assign_participant_split("participant-001", salt="salt-a") == first
    assignments_a = [assign_participant_split(f"p-{value}", salt="salt-a") for value in range(100)]
    assignments_b = [assign_participant_split(f"p-{value}", salt="salt-b") for value in range(100)]
    assert assignments_a != assignments_b


def test_detects_manual_identity_leakage() -> None:
    with pytest.raises(ValueError, match="appears in"):
        assert_no_participant_leakage(
            {
                DatasetSplit.TRAIN: [{"participant_id": "participant-1"}],
                DatasetSplit.VALIDATION: [{"participant_id": "participant-1"}],
                DatasetSplit.TEST: [],
            }
        )


@pytest.mark.parametrize(
    "thresholds",
    [SplitThresholds(0.7, 0.15), SplitThresholds(0.6, 0.2)],
)
def test_all_splits_receive_participants(thresholds: SplitThresholds) -> None:
    assigned = {
        assign_participant_split(f"participant-{value}", salt="study", thresholds=thresholds)
        for value in range(500)
    }
    assert assigned == set(DatasetSplit)


@pytest.mark.parametrize("train,validation", [(0, 0.2), (0.8, 0.2), (1.1, 0.1)])
def test_rejects_invalid_split_thresholds(train: float, validation: float) -> None:
    with pytest.raises(ValueError):
        SplitThresholds(train, validation)
