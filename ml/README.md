# NailSize ML Tooling

This directory owns research-dataset schemas, participant-level split enforcement, annotation quality, training, evaluation, export, and model-card artifacts. It must never contain production uploads, direct identifiers, or unconsented photos.

The current tooling establishes the data contract. Model training begins only after an approved, consented dataset is available. Synthetic fixtures may test code but cannot support accuracy claims.

## Evaluation contract

`nailsize_ml.evaluation` computes mask IoU/Dice together with symmetric mean and p95 boundary error, then evaluates physical-width MAE, p90 error, signed bias, exact-size accuracy, adjacent-size accuracy, and severe miss rate against the release thresholds in `outputs/plan.md`. Paired empty masks are perfect agreement; a one-sided empty mask has infinite boundary error and therefore cannot silently pass.

The planned baseline remains TorchVision's `deeplabv3_mobilenet_v3_large`. TorchVision documents segmentation builders as beta APIs, so the eventual training environment must pin the tested PyTorch/TorchVision pair. Export must use PyTorch's recommended `torch.export`-based ONNX path (`dynamo=True`) and compare native and ONNX Runtime outputs before publishing a model artifact.

- [TorchVision DeepLabV3 builders](https://docs.pytorch.org/vision/stable/models/deeplabv3.html)
- [PyTorch ONNX exporter](https://docs.pytorch.org/docs/stable/onnx.html)

Install the pinned research toolchain separately from the production API:

```bash
python -m pip install -e 'ml[training]'
pytest ml/tests/test_modeling.py
```

`build_deeplab_mobilenet()` creates the one-channel baseline without altering the production runtime. `export_verified_onnx()` exports the fixed `1x3x224x160` input and `1x1x224x160` logits output, writes required model-version metadata, validates the ONNX graph, executes it with ONNX Runtime, and fails if native/exported outputs differ beyond the configured tolerance. Synthetic export tests validate this machinery but do not constitute a trained model.

Training consumes a JSON Lines manifest outside Git. Each record must contain `image_id`, `participant_id`, `split`, `image_path`, and `mask_path`; paths are relative to the approved dataset root. The loader rejects duplicate images, participant leakage between splits, absolute paths, root escapes, and missing files. Example:

```json
{"image_id":"crop-001","participant_id":"study-001","split":"train","image_path":"images/crop-001.png","mask_path":"masks/crop-001.png"}
```

```bash
nailsize-train \
  --manifest /approved-data/manifest.jsonl \
  --dataset-root /approved-data \
  --checkpoint /research-artifacts/baseline.pt \
  --model-version baseline-YYYYMMDD
```

The command fixes preprocessing to the production tensor contract, enables deterministic algorithms, records configuration/loss history/PyTorch version in the checkpoint, and never writes source images into the repository. A checkpoint is a research artifact, not a releasable model; evaluation, ONNX export, model-card review, and release gates still follow training.
