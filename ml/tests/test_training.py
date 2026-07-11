import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")
from PIL import Image  # noqa: E402

from nailsize_ml.dataset import DatasetSplit  # noqa: E402
from nailsize_ml.training import (  # noqa: E402
    NailSegmentationDataset,
    TrainingExample,
    load_training_manifest,
    set_reproducible_seed,
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


def test_loads_participant_safe_manifest_and_fixed_preprocessing(tmp_path: Path) -> None:
    image_path, mask_path = write_pair(tmp_path, "sample")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "image_id": "image-001",
                "participant_id": "participant-001",
                "split": "train",
                "image_path": image_path.name,
                "mask_path": mask_path.name,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    examples = load_training_manifest(manifest, tmp_path)
    image, mask = NailSegmentationDataset(examples)[0]
    assert image.shape == (3, 224, 160)
    assert image.dtype == torch.float32
    assert mask.shape == (1, 224, 160)
    assert set(torch.unique(mask).tolist()) == {0.0, 1.0}


def test_manifest_rejects_participant_leakage_and_path_escape(tmp_path: Path) -> None:
    image_path, mask_path = write_pair(tmp_path, "sample")
    records = [
        {
            "image_id": f"image-{index}",
            "participant_id": "participant-001",
            "split": split,
            "image_path": image_path.name,
            "mask_path": mask_path.name,
        }
        for index, split in enumerate(("train", "validation"), 1)
    ]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    with pytest.raises(ValueError, match="appears"):
        load_training_manifest(manifest, tmp_path)

    records[1]["participant_id"] = "participant-002"
    records[1]["image_path"] = "../outside.png"
    manifest.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_training_manifest(manifest, tmp_path)


def test_seed_and_train_epoch_are_deterministic(tmp_path: Path) -> None:
    image_path, mask_path = write_pair(tmp_path, "sample")
    example = TrainingExample(
        "image-001", "participant-001", DatasetSplit.TRAIN, image_path, mask_path
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
