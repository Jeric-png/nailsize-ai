# NailSize ML Tooling

This directory owns research-dataset schemas, participant-level split enforcement, annotation quality, training, evaluation, export, and model-card artifacts. It must never contain production uploads, direct identifiers, or unconsented photos.

The current tooling establishes the data contract. Model training begins only after an approved, consented dataset is available. Synthetic fixtures may test code but cannot support accuracy claims.

## Evaluation contract

`nailsize_ml.evaluation` computes mask IoU/Dice together with symmetric mean and p95 boundary error, then evaluates physical-width MAE, p90 error, signed bias, exact-size accuracy, adjacent-size accuracy, and severe miss rate against the release thresholds in `outputs/plan.md`. Paired empty masks are perfect agreement; a one-sided empty mask has infinite boundary error and therefore cannot silently pass.

The planned baseline remains TorchVision's `deeplabv3_mobilenet_v3_large`. TorchVision documents segmentation builders as beta APIs, so the eventual training environment must pin the tested PyTorch/TorchVision pair. Export must use PyTorch's recommended `torch.export`-based ONNX path (`dynamo=True`) and compare native and ONNX Runtime outputs before publishing a model artifact.

- [TorchVision DeepLabV3 builders](https://docs.pytorch.org/vision/stable/models/deeplabv3.html)
- [PyTorch ONNX exporter](https://docs.pytorch.org/docs/stable/onnx.html)
