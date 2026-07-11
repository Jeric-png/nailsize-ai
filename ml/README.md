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

## Accuracy release report

Run `nailsize-accuracy-report observations.jsonl --adequate-cohort skin_tone=monk-5 --adequate-cohort curvature=medium --adequate-cohort width=medium --adequate-cohort device=phone-a --output accuracy-report.json` after the public holdout is locked. Each JSONL row must contain `participant_id`, predicted and ground-truth width/size fields, and a `cohorts` string map. The report enforces the 200-participant/2,000-nail minimum, all overall measurement gates, reviewer-declared adequately sampled cohort gates across skin tone, curvature, width, and device, and deterministic participant-clustered 95% bootstrap intervals. It exits non-zero unless every available gate passes. Declaring cohort adequacy remains a documented study-review decision; the tool never infers adequacy from an arbitrary count.

Run `nailsize-model-card model-metadata.json accuracy-report.json model-card.md` only after review. Publication fails unless the accuracy report passes and metadata includes the immutable model checksum/version, dataset version, intended use, out-of-scope cases, limitations, overlap and boundary metrics, ONNX parity at or below `1e-4`, and named model-owner, nail-tech, and privacy/security reviews. The generated Markdown embeds overall clustered intervals and adequately sampled cohort results.

Run `nailsize-operational-report study-bundle.json --output operational-report.json` on the locked study export. The bundle must declare `"schema_version": "nailsize-operational-study@1"` and contain one completion outcome per participant, ground-truth validity decisions, two complete ten-nail capture sets per repeatability participant, adequately sampled cohort declarations with parity-review references, and a repeatability-review reference. The report enforces first-pass and one-retake completion plus false-acceptance/false-rejection gates, publishes participant-clustered 95% intervals, and reports repeated-capture differences and subgroup rejection-rate gaps. Because the plan defines no universal numeric repeatability or subgroup rejection-parity threshold, those two conclusions require named study reviews instead of an invented cutoff. No images belong in this bundle.

Before publishing a GitHub model release, place only `nail-segmentation.onnx`, `model-metadata.json`, `accuracy-report.json`, `operational-report.json`, and the generated `model-card.md` in one directory, then run:

```bash
nailsize-release-bundle /approved-release \
  --expected-model-version MODEL_VERSION \
  --expected-model-sha256 MODEL_SHA256 \
  --output /reports/model-release-manifest.json
```

This final gate independently checks exact contents, checksum/version identity, every numeric accuracy and operational threshold, finite clustered intervals, study/cohort counts and reviews, model-card reproducibility, ONNX parity metadata, and positive boundary uncertainty. It emits metadata only. Passing it proves the bundle is internally consistent; it does not prove that the submitted study data was representative or honestly collected, so protected human review remains mandatory.

The default CI suite measures coverage for production and dependency-light ML modules; the heavy PyTorch modules are excluded because their optional dependencies are not installed there. Run the `Model Tooling` GitHub Actions workflow after changes to `modeling.py`, `training.py`, or their pinned dependencies. It installs the research extra on Linux and executes the real factory/export/training tests.

Benchmark the exported candidate inside the exact Cloud Run container/revision before approval:

```bash
nailsize-benchmark /models/nail-segmentation.onnx \
  --iterations 200 \
  --warmup-iterations 20 \
  --output /reports/onnx-benchmark.json
```

The report includes the model checksum, ONNX Runtime provider, iteration counts, p50/p95/p99/mean latency, logical CPU count, machine/platform, and Python version. A laptop or generic CI result only verifies the harness; only a report from the configured 2-vCPU/4-GiB Cloud Run revision satisfies the deployment benchmark task.
