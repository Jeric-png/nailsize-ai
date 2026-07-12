import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")
from PIL import Image  # noqa: E402

import nailsize_ml.training as training  # noqa: E402
from nailsize_ml.dataset import DatasetSplit  # noqa: E402
from nailsize_ml.dataset_provenance import (  # noqa: E402
    COLLECTION_CHANNEL,
    CONSENT_STATUS,
    ResearchDatasetApproval,
    build_research_dataset_report,
    verify_research_dataset_report,
)
from nailsize_ml.holdout_lock import HoldoutLockApproval  # noqa: E402
from nailsize_ml.training import (  # noqa: E402
    NailSegmentationDataset,
    TrainingConfig,
    TrainingExample,
    load_training_manifest,
    set_reproducible_seed,
    train_baseline,
    train_epoch,
)


def write_pair(root: Path, name: str) -> tuple[Path, Path]:
    image_path = root / f"{name}.png"
    mask_path = root / f"{name}-mask.png"
    Image.fromarray(np.full((32, 24, 3), 128, dtype=np.uint8)).save(image_path)
    mask = np.zeros((32, 24), dtype=np.uint8)
    mask[8:24, 6:18] = 255
    Image.fromarray(mask).save(mask_path)
    return image_path, mask_path


def manifest_record(image_path: Path, mask_path: Path, **overrides) -> dict:
    record = {
        "image_id": "image-001",
        "participant_id": "participant-001",
        "split": "train",
        "image_path": image_path.name,
        "mask_path": mask_path.name,
        "dataset_version": "study-1",
        "data_origin": COLLECTION_CHANNEL,
        "consent_status": CONSENT_STATUS,
    }
    record.update(overrides)
    return record


def approve_manifest(manifest: Path) -> ResearchDatasetApproval:
    report_path = manifest.with_suffix(".provenance.json")
    report = build_research_dataset_report(
        manifest,
        dataset_version="study-1",
        research_approval_ref="research-review-1",
        production_exclusion_review_ref="privacy-review-1",
    )
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    checksum = hashlib.sha256(report_path.read_bytes()).hexdigest()
    return verify_research_dataset_report(
        report_path, manifest, expected_provenance_sha256=checksum
    )


def approval_for(examples: list[TrainingExample]) -> ResearchDatasetApproval:
    participants = {example.participant_id for example in examples}
    return ResearchDatasetApproval(
        dataset_version="study-1",
        provenance_sha256="a" * 64,
        manifest_sha256="b" * 64,
        record_count=len(examples),
        participant_count=len(participants),
        split_record_counts={
            split.value: sum(example.split == split for example in examples)
            for split in DatasetSplit
        },
        split_participant_counts={
            split.value: len(
                {example.participant_id for example in examples if example.split == split}
            )
            for split in DatasetSplit
        },
        research_approval_ref="research-review-1",
        production_exclusion_review_ref="privacy-review-1",
    )


def holdout_for(approval: ResearchDatasetApproval) -> HoldoutLockApproval:
    return HoldoutLockApproval(
        dataset_version=approval.dataset_version,
        lock_sha256="d" * 64,
        manifest_sha256=approval.manifest_sha256,
        split_salt_id="split-salt-1",
        test_record_count=approval.split_record_counts[DatasetSplit.TEST],
        test_participant_count=approval.split_participant_counts[DatasetSplit.TEST],
        test_set_commitment_sha256="e" * 64,
        holdout_lock_review_ref="holdout-review-1",
    )


def test_loads_participant_safe_manifest_and_fixed_preprocessing(tmp_path: Path) -> None:
    pairs = [write_pair(tmp_path, f"sample-{index}") for index in range(3)]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "".join(
            json.dumps(
                manifest_record(
                    image_path,
                    mask_path,
                    image_id=f"image-{index}",
                    participant_id=f"participant-{index}",
                    split=split,
                )
            )
            + "\n"
            for index, ((image_path, mask_path), split) in enumerate(
                zip(pairs, DatasetSplit, strict=True), 1
            )
        ),
        encoding="utf-8",
    )
    approval = approve_manifest(manifest)
    examples = load_training_manifest(
        manifest,
        tmp_path,
        dataset_approval=approval,
        holdout_lock_approval=holdout_for(approval),
    )
    image, mask = NailSegmentationDataset(examples)[0]
    assert image.shape == (3, 224, 160)
    assert image.dtype == torch.float32
    assert mask.shape == (1, 224, 160)
    assert set(torch.unique(mask).tolist()) == {0.0, 1.0}


def test_manifest_rejects_participant_leakage_and_path_escape(tmp_path: Path) -> None:
    image_path, mask_path = write_pair(tmp_path, "sample")
    records = [
        manifest_record(
            image_path,
            mask_path,
            image_id=f"image-{index}",
            participant_id="participant-001",
            split=split,
        )
        for index, split in enumerate(("train", "validation"), 1)
    ]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    with pytest.raises(ValueError, match="appears"):
        approve_manifest(manifest)

    records[1]["participant_id"] = "participant-002"
    records[1]["image_path"] = "../outside.png"
    manifest.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        approval = approve_manifest(manifest)
        load_training_manifest(
            manifest,
            tmp_path,
            dataset_approval=approval,
            holdout_lock_approval=holdout_for(approval),
        )


def test_manifest_rejects_approval_with_mismatched_aggregates(tmp_path: Path) -> None:
    image_path, mask_path = write_pair(tmp_path, "sample")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps(manifest_record(image_path, mask_path)) + "\n", encoding="utf-8")
    approval = approve_manifest(manifest)

    with pytest.raises(ValueError, match="approved dataset aggregates"):
        holdout = holdout_for(approval)
        load_training_manifest(
            manifest,
            tmp_path,
            dataset_approval=replace(approval, record_count=approval.record_count + 1),
            holdout_lock_approval=holdout,
        )


def test_seed_and_train_epoch_are_deterministic(tmp_path: Path) -> None:
    image_path, mask_path = write_pair(tmp_path, "sample")
    example = TrainingExample(
        "image-001",
        "participant-001",
        DatasetSplit.TRAIN,
        image_path,
        mask_path,
        "study-1",
    )
    dataset = NailSegmentationDataset([example])
    loader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False)

    def run_once() -> tuple[float, torch.Tensor]:
        set_reproducible_seed(9)
        model = torch.nn.Conv2d(3, 1, kernel_size=1)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
        loss = train_epoch(model, loader, optimizer, device="cpu")
        return loss, model.weight.detach().clone()

    first_loss, first_weight = run_once()
    second_loss, second_weight = run_once()
    assert first_loss == pytest.approx(second_loss)
    assert torch.equal(first_weight, second_weight)


def test_training_checkpoint_is_safe_weights_only_data(tmp_path: Path, monkeypatch) -> None:
    train_image, train_mask = write_pair(tmp_path, "train")
    test_image, test_mask = write_pair(tmp_path, "test")
    examples = [
        TrainingExample(
            "image-001",
            "participant-001",
            DatasetSplit.TRAIN,
            train_image,
            train_mask,
            "study-1",
        ),
        TrainingExample(
            "image-002",
            "participant-002",
            DatasetSplit.TEST,
            test_image,
            test_mask,
            "study-1",
        ),
    ]
    monkeypatch.setattr(
        training,
        "build_deeplab_mobilenet",
        lambda *, pretrained_backbone: torch.nn.Conv2d(3, 1, kernel_size=1),
    )
    checkpoint = tmp_path / "candidate.pt"

    approval = approval_for(examples)
    train_baseline(
        examples,
        TrainingConfig(
            model_version="candidate-1",
            epochs=1,
            batch_size=1,
            pretrained_backbone=False,
        ),
        checkpoint,
        dataset_approval=approval,
        holdout_lock_approval=holdout_for(approval),
    )

    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert payload["config"]["model_version"] == "candidate-1"
    assert payload["torch_version"] == str(torch.__version__)
    assert type(payload["torch_version"]) is str
    assert payload["dataset_version"] == "study-1"
    assert payload["dataset_provenance_sha256"] == "a" * 64
    assert payload["training_manifest_sha256"] == "b" * 64
    assert payload["holdout_lock_sha256"] == "d" * 64
