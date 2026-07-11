import argparse
import json
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .dataset import DatasetSplit, assert_no_participant_leakage
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
    manifest_path: str | Path, dataset_root: str | Path
) -> tuple[TrainingExample, ...]:
    manifest = Path(manifest_path)
    root = Path(dataset_root).resolve()
    if not manifest.is_file() or not root.is_dir():
        raise ValueError("Manifest file and dataset root are required")

    examples: list[TrainingExample] = []
    seen_image_ids: set[str] = set()
    with manifest.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                image_id = str(record["image_id"]).strip()
                participant_id = str(record["participant_id"]).strip()
                split = DatasetSplit(str(record["split"]))
                image_path = _dataset_path(root, record["image_path"])
                mask_path = _dataset_path(root, record["mask_path"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"Invalid training manifest record on line {line_number}"
                ) from error
            if not image_id or not participant_id or image_id in seen_image_ids:
                raise ValueError(f"Invalid or duplicate image ID on line {line_number}")
            if not image_path.is_file() or not mask_path.is_file():
                raise ValueError(f"Missing image or mask on line {line_number}")
            seen_image_ids.add(image_id)
            examples.append(TrainingExample(image_id, participant_id, split, image_path, mask_path))
    if not examples:
        raise ValueError("Training manifest must contain at least one example")

    split_records = {
        split: [
            {"participant_id": example.participant_id}
            for example in examples
            if example.split == split
        ]
        for split in DatasetSplit
    }
    assert_no_participant_leakage(split_records)
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
    device: str = "cpu",
) -> tuple[float, ...]:
    try:
        import torch
        from torch.utils.data import DataLoader
    except ImportError as error:
        raise RuntimeError("Install nailsize-ml-tooling[training] to train the model") from error
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
            "losses": losses,
            "torch_version": str(torch.__version__),
        },
        destination,
    )
    return losses


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
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-pretrained-backbone", action="store_true")
    arguments = parser.parse_args()
    examples = load_training_manifest(arguments.manifest, arguments.dataset_root)
    config = TrainingConfig(
        model_version=arguments.model_version,
        seed=arguments.seed,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        learning_rate=arguments.learning_rate,
        pretrained_backbone=not arguments.no_pretrained_backbone,
    )
    losses = train_baseline(examples, config, arguments.checkpoint, device=arguments.device)
    print(json.dumps({"checkpoint": str(arguments.checkpoint), "losses": losses}))


if __name__ == "__main__":
    main()
