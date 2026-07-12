import argparse
import json
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .dataset import DatasetSplit, assert_no_participant_leakage
from .dataset_provenance import (
    ResearchDatasetApproval,
    validate_research_manifest,
    verify_research_dataset_report,
)
from .holdout_lock import HoldoutLockApproval, verify_holdout_lock_report
from .modeling import INPUT_HEIGHT, INPUT_WIDTH, build_deeplab_mobilenet, combined_segmentation_loss

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True)
class TrainingExample:
    image_id: str
    participant_id: str
    split: DatasetSplit
    image_path: Path
    mask_path: Path
    dataset_version: str


@dataclass(frozen=True)
class TrainingConfig:
    model_version: str
    seed: int = 1729
    epochs: int = 20
    batch_size: int = 8
    learning_rate: float = 0.0001
    pretrained_backbone: bool = True

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("Model version is required")
        if self.seed < 0 or self.epochs <= 0 or self.batch_size <= 0 or self.learning_rate <= 0:
            raise ValueError("Training configuration values are out of range")


def load_training_manifest(
    manifest_path: str | Path,
    dataset_root: str | Path,
    *,
    dataset_approval: ResearchDatasetApproval,
    holdout_lock_approval: HoldoutLockApproval,
) -> tuple[TrainingExample, ...]:
    manifest = Path(manifest_path)
    root = Path(dataset_root).resolve()
    if not manifest.is_file() or not root.is_dir():
        raise ValueError("Manifest file and dataset root are required")

    records = validate_research_manifest(
        manifest, expected_dataset_version=dataset_approval.dataset_version
    )
    examples: list[TrainingExample] = []
    for line_number, record in enumerate(records, 1):
        try:
            image_path = _dataset_path(root, record["image_path"])
            mask_path = _dataset_path(root, record["mask_path"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid training manifest record on line {line_number}") from error
        if not image_path.is_file() or not mask_path.is_file():
            raise ValueError(f"Missing image or mask on line {line_number}")
        examples.append(
            TrainingExample(
                record["image_id"],
                record["participant_id"],
                DatasetSplit(record["split"]),
                image_path,
                mask_path,
                record["dataset_version"],
            )
        )

    split_records = {
        split: [
            {"participant_id": example.participant_id}
            for example in examples
            if example.split == split
        ]
        for split in DatasetSplit
    }
    assert_no_participant_leakage(split_records)
    _validate_dataset_approval(examples, dataset_approval)
    _validate_holdout_lock(examples, dataset_approval, holdout_lock_approval)
    return tuple(examples)


class NailSegmentationDataset:
    def __init__(self, examples: Sequence[TrainingExample]) -> None:
        if not examples:
            raise ValueError("At least one training example is required")
        self.examples = tuple(examples)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int):
        try:
            import torch
            from PIL import Image
        except ImportError as error:
            raise RuntimeError(
                "Install nailsize-ml-tooling[training] to load training data"
            ) from error
        example = self.examples[index]
        with Image.open(example.image_path) as source:
            rgb = np.asarray(
                source.convert("RGB").resize(
                    (INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR
                ),
                dtype=np.uint8,
            ).copy()
        with Image.open(example.mask_path) as source:
            mask = np.asarray(
                source.convert("L").resize((INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.NEAREST),
                dtype=np.uint8,
            ).copy()
        normalized = (rgb.astype(np.float32) / 255.0 - _MEAN) / _STD
        image_tensor = torch.from_numpy(normalized.transpose(2, 0, 1).copy())
        mask_tensor = torch.from_numpy((mask > 0).astype(np.float32)[None, ...])
        return image_tensor, mask_tensor


def set_reproducible_seed(seed: int) -> None:
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to train the model") from error
    if seed < 0:
        raise ValueError("Seed must be non-negative")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def train_epoch(model: Any, loader: Any, optimizer: Any, *, device: str) -> float:
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to train the model") from error
    model.train()
    total_loss = 0.0
    batch_count = 0
    for images, masks in loader:
        images = images.to(device)
        masks = masks.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = combined_segmentation_loss(logits, masks)
        if not torch.isfinite(loss):
            raise RuntimeError("Training loss became non-finite")
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu())
        batch_count += 1
    if batch_count == 0:
        raise ValueError("Training loader produced no batches")
    return total_loss / batch_count


def train_baseline(
    examples: Sequence[TrainingExample],
    config: TrainingConfig,
    checkpoint_path: str | Path,
    *,
    dataset_approval: ResearchDatasetApproval,
    holdout_lock_approval: HoldoutLockApproval,
    device: str = "cpu",
) -> tuple[float, ...]:
    try:
        import torch
        from torch.utils.data import DataLoader
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to train the model") from error
    _validate_dataset_approval(examples, dataset_approval)
    _validate_holdout_lock(examples, dataset_approval, holdout_lock_approval)
    train_examples = [example for example in examples if example.split == DatasetSplit.TRAIN]
    if not train_examples:
        raise ValueError("Training split is empty")
    set_reproducible_seed(config.seed)
    generator = torch.Generator().manual_seed(config.seed)
    loader = DataLoader(
        NailSegmentationDataset(train_examples),
        batch_size=config.batch_size,
        shuffle=True,
        generator=generator,
        num_workers=0,
    )
    model = build_deeplab_mobilenet(pretrained_backbone=config.pretrained_backbone).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)
    losses = tuple(
        train_epoch(model, loader, optimizer, device=device) for _ in range(config.epochs)
    )
    destination = Path(checkpoint_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "config": asdict(config),
            "training_examples": len(train_examples),
            "dataset_version": dataset_approval.dataset_version,
            "dataset_provenance_sha256": dataset_approval.provenance_sha256,
            "training_manifest_sha256": dataset_approval.manifest_sha256,
            "holdout_lock_sha256": holdout_lock_approval.lock_sha256,
            "losses": losses,
            "torch_version": str(torch.__version__),
        },
        destination,
    )
    return losses


def _validate_dataset_approval(
    examples: Sequence[TrainingExample], approval: ResearchDatasetApproval
) -> None:
    if not examples:
        raise ValueError("Training manifest must contain at least one example")
    if any(example.dataset_version != approval.dataset_version for example in examples):
        raise ValueError("Training examples do not match the approved dataset version")
    participants = {example.participant_id for example in examples}
    split_records = {
        split.value: sum(example.split == split for example in examples) for split in DatasetSplit
    }
    split_participants = {
        split.value: len({example.participant_id for example in examples if example.split == split})
        for split in DatasetSplit
    }
    if (
        len(examples) != approval.record_count
        or len(participants) != approval.participant_count
        or split_records != approval.split_record_counts
        or split_participants != approval.split_participant_counts
    ):
        raise ValueError("Training examples do not match approved dataset aggregates")


def _validate_holdout_lock(
    examples: Sequence[TrainingExample],
    dataset_approval: ResearchDatasetApproval,
    holdout_lock: HoldoutLockApproval,
) -> None:
    if (
        not _valid_sha256(holdout_lock.lock_sha256)
        or not _valid_sha256(holdout_lock.test_set_commitment_sha256)
        or holdout_lock.test_record_count <= 0
        or holdout_lock.test_participant_count <= 0
    ):
        raise ValueError("Public holdout lock approval is invalid")
    if (
        holdout_lock.dataset_version != dataset_approval.dataset_version
        or holdout_lock.manifest_sha256 != dataset_approval.manifest_sha256
    ):
        raise ValueError("Holdout lock does not match the approved research dataset")
    test_examples = [example for example in examples if example.split == DatasetSplit.TEST]
    test_participants = {example.participant_id for example in test_examples}
    if (
        len(test_examples) != holdout_lock.test_record_count
        or len(test_participants) != holdout_lock.test_participant_count
    ):
        raise ValueError("Training manifest does not match the locked public holdout")


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _dataset_path(root: Path, value: Any) -> Path:
    relative = Path(str(value))
    if relative.is_absolute():
        raise ValueError("Dataset paths must be relative")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("Dataset path escapes the approved root") from error
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the NailSize segmentation baseline")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--dataset-provenance-report", required=True, type=Path)
    parser.add_argument("--expected-dataset-provenance-sha256", required=True)
    parser.add_argument("--holdout-lock-report", required=True, type=Path)
    parser.add_argument("--expected-holdout-lock-sha256", required=True)
    parser.add_argument("--split-salt-file", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-pretrained-backbone", action="store_true")
    arguments = parser.parse_args()
    approval = verify_research_dataset_report(
        arguments.dataset_provenance_report,
        arguments.manifest,
        expected_provenance_sha256=arguments.expected_dataset_provenance_sha256,
    )
    holdout_lock = verify_holdout_lock_report(
        arguments.holdout_lock_report,
        arguments.manifest,
        split_salt_path=arguments.split_salt_file,
        expected_lock_sha256=arguments.expected_holdout_lock_sha256,
    )
    examples = load_training_manifest(
        arguments.manifest,
        arguments.dataset_root,
        dataset_approval=approval,
        holdout_lock_approval=holdout_lock,
    )
    config = TrainingConfig(
        model_version=arguments.model_version,
        seed=arguments.seed,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        learning_rate=arguments.learning_rate,
        pretrained_backbone=not arguments.no_pretrained_backbone,
    )
    losses = train_baseline(
        examples,
        config,
        arguments.checkpoint,
        dataset_approval=approval,
        holdout_lock_approval=holdout_lock,
        device=arguments.device,
    )
    print(json.dumps({"checkpoint": str(arguments.checkpoint), "losses": losses}))


if __name__ == "__main__":
    main()
