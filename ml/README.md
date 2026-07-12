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

`build_deeplab_mobilenet()` creates the one-channel baseline without altering the production runtime. `export_verified_onnx()` exports the fixed `1x3x224x160` input and `1x1x224x160` logits output, writes required model-version metadata, validates the ONNX graph, executes it with ONNX Runtime, and fails if native/exported outputs differ beyond the configured tolerance. It publishes the ONNX file atomically only after parity succeeds. Synthetic export tests validate this machinery but do not constitute a trained model.

Training consumes an exact JSON Lines manifest outside Git. Every record must identify the locked dataset and declare the only accepted source/consent boundary; paths are relative to the approved dataset root. The loader rejects extra fields, production-origin or non-active-consent records, mixed dataset versions, duplicate images, participant leakage between splits, absolute paths, root escapes, and missing files. Example:

```json
{
  "image_id": "crop-001",
  "participant_id": "study-001",
  "split": "train",
  "image_path": "images/crop-001.png",
  "mask_path": "masks/crop-001.png",
  "dataset_version": "study-2026-01",
  "data_origin": "approved_research_study",
  "consent_status": "active_research_consent"
}
```

```bash
nailsize-dataset-provenance-report /approved-data/manifest.jsonl \
  --dataset-version study-2026-01 \
  --research-approval-ref RESEARCH_REVIEW \
  --production-exclusion-review-ref PRIVACY_REVIEW \
  --output /approved-data/dataset-provenance-report.json

DATASET_PROVENANCE_SHA256="$(shasum -a 256 /approved-data/dataset-provenance-report.json | cut -d ' ' -f 1)"

nailsize-holdout-lock /approved-data/manifest.jsonl \
  --dataset-version study-2026-01 \
  --split-salt-file /approved-secrets/split-salt \
  --split-salt-id split-salt-2026-01 \
  --holdout-lock-review-ref HOLDOUT_REVIEW \
  --output /approved-data/holdout-lock-report.json

HOLDOUT_LOCK_SHA256="$(shasum -a 256 /approved-data/holdout-lock-report.json | cut -d ' ' -f 1)"

nailsize-train \
  --manifest /approved-data/manifest.jsonl \
  --dataset-root /approved-data \
  --dataset-provenance-report /approved-data/dataset-provenance-report.json \
  --expected-dataset-provenance-sha256 "$DATASET_PROVENANCE_SHA256" \
  --holdout-lock-report /approved-data/holdout-lock-report.json \
  --expected-holdout-lock-sha256 "$HOLDOUT_LOCK_SHA256" \
  --split-salt-file /approved-secrets/split-salt \
  --checkpoint /research-artifacts/baseline.pt \
  --model-version baseline-YYYYMMDD
```

The aggregate reports contain counts, checksums, dataset identity, and named reviews only—never participant IDs, image IDs, paths, consent records, or the protected split salt. The salt file must contain the exact secret value without trailing whitespace and must remain outside Git and release artifacts. Training requires both independently approved report checksums, revalidates the manifest and every deterministic participant split, fixes preprocessing to the production tensor contract, enables deterministic algorithms, and carries the dataset/provenance/manifest/holdout-lock checksums into the checkpoint. The public test split must not be inspected for architecture selection, threshold tuning, or relabeling. Training never writes source images into the repository. A checkpoint is a research artifact, not a releasable model; evaluation, ONNX export, model-card review, and release gates still follow training.

After the model owner selects a checkpoint using the locked validation protocol, record its SHA-256 and export that exact file into a new empty evidence directory:

```bash
nailsize-export-checkpoint /approved/checkpoints/candidate.pt \
  --expected-checkpoint-sha256 "$CHECKPOINT_SHA256" \
  --model-version "$MODEL_VERSION" \
  --onnx /approved/export/nail-segmentation.onnx \
  --report /approved/evidence/onnx-export-report.json
```

The exporter safely loads only the checksum-approved checkpoint, reconstructs the fixed DeepLabV3-MobileNetV3 architecture without downloading weights, requires strict state-dictionary compatibility, and verifies native/ONNX parity on CPU. It refuses pre-existing or overlapping output paths and emits neither artifact unless both the ONNX model and machine-readable evidence can be published. The report locks checkpoint/model checksums, dataset/provenance/manifest/holdout-lock checksums, versions, tensor shapes, training counts/loss, provider, and measured parity. Copy its measured parity and ONNX checksum into the independently reviewed `model-metadata.json`, then preserve the original `onnx-export-report.json` unchanged in the release bundle so the final gate can verify that linkage.

## Accuracy release report

Run `nailsize-annotation-report annotation-study.json --first-mask-root /private/technician-a --second-mask-root /private/technician-b --output annotation-agreement-report.json` before model approval. The versioned study bundle contains the two annotation sets, total dataset item count, material-disagreement adjudications, explicitly disputed boundary IDs, and named agreement/adjudication review references. Each `mask_uri` resolves to a bounded, non-pickled `.npy` mask beneath its technician-specific root. The report requires two independent technicians, at least 10% double annotation, third-party adjudication for categorical disagreements, width differences over 0.5 mm, and reviewer-declared boundary disputes. It publishes counts and aggregate Dice, boundary-distance, label, size, kappa, and width-difference metrics without retaining participant, image, technician, mask, or adjudicator identifiers. The plan defines no universal agreement threshold, so the tool requires a named review instead of inventing one.

Run `nailsize-accuracy-report observations.jsonl --adequate-cohort skin_tone=monk-5 --adequate-cohort curvature=medium --adequate-cohort width=medium --adequate-cohort device=phone-a --output accuracy-report.json` after the public holdout is locked. Each JSONL row must contain `participant_id`, predicted and ground-truth width/size fields, and a `cohorts` string map. The report enforces the 200-participant/2,000-nail minimum, all overall measurement gates, reviewer-declared adequately sampled cohort gates across skin tone, curvature, width, and device, and deterministic participant-clustered 95% bootstrap intervals. It exits non-zero unless every available gate passes. Declaring cohort adequacy remains a documented study-review decision; the tool never infers adequacy from an arbitrary count.

Run the selected ONNX model over every locked test crop, preserve `224×160` probability arrays and adjudicated binary ground-truth masks under separate approved roots, and create exact JSONL rows containing only `participant_id`, `image_id`, `prediction_probability_uri`, and `ground_truth_mask_uri`. Then generate the aggregate segmentation evidence:

```bash
nailsize-segmentation-report segmentation-observations.jsonl \
  --prediction-mask-root /approved-evaluation/predictions \
  --ground-truth-mask-root /approved-evaluation/ground-truth \
  --dataset-version "$DATASET_VERSION" \
  --model-version "$MODEL_VERSION" \
  --model-sha256 "$MODEL_SHA256" \
  --holdout-lock-report /approved-data/holdout-lock-report.json \
  --expected-holdout-lock-sha256 "$HOLDOUT_LOCK_SHA256" \
  --prediction-threshold 0.5 \
  --threshold-selection-ref VALIDATION_THRESHOLD_REVIEW \
  --segmentation-review-ref SEGMENTATION_REVIEW \
  --output segmentation-evaluation-report.json
```

The tool accepts only bounded, finite, non-pickled `.npy` arrays with the fixed model output shape, requires probabilities within `[0, 1]` and binary ground truth, and applies the recorded threshold itself. It requires the observation identities and counts to reproduce the approved holdout commitment, reports mean IoU/Dice plus mean and conservative p95 nail-boundary error with participant-clustered intervals, and emits no identifiers or paths. The prediction threshold must be selected on validation data before public-holdout access; the report records a named threshold review rather than tuning on test results. Because the plan defines no universal segmentation threshold, a named segmentation review is mandatory and the report does not invent a pass line.

Run `nailsize-model-card model-metadata.json accuracy-report.json model-card.md` only after review. Publication fails unless the accuracy report passes and metadata includes the immutable model checksum/version, dataset version, intended use, out-of-scope cases, limitations, overlap and boundary metrics, ONNX parity at or below `1e-4`, and named model-owner, nail-tech, and privacy/security reviews. The generated Markdown embeds overall clustered intervals and adequately sampled cohort results.

Run `nailsize-operational-report study-bundle.json --output operational-report.json` on the locked study export. The bundle must declare `"schema_version": "nailsize-operational-study@1"` and contain one completion outcome per participant, ground-truth validity decisions, two complete ten-nail capture sets per repeatability participant, adequately sampled cohort declarations with parity-review references, and a repeatability-review reference. The report enforces first-pass and one-retake completion plus false-acceptance/false-rejection gates, publishes participant-clustered 95% intervals, and reports repeated-capture differences and subgroup rejection-rate gaps. Because the plan defines no universal numeric repeatability or subgroup rejection-parity threshold, those two conclusions require named study reviews instead of an invented cutoff. No images belong in this bundle.

Run `nailsize-size-calibration-report physical-best-fit.jsonl --dataset-version DATASET_VERSION --calibration-review-ref REVIEW --curvature-review medium=REVIEW --output size-calibration-report.json` on the same locked public holdout. Each exact JSONL row contains only an opaque participant/nail ID, adjudicated physical width, physical best-fit size, and curvature cohort. The report applies the exact immutable `platform-default@1` mapping to physical widths, enforces the 200-participant/2,000-nail and size-agreement gates, rejects unmappable widths, publishes participant-clustered intervals, and measures best-fit tip margin overall and for reviewer-declared adequately sampled curvature cohorts. Cohort exact-size accuracy may not trail overall by more than five percentage points. Named reviews remain mandatory because the plan does not define a universal acceptable curvature-margin threshold.

Before publishing a GitHub model release, place only `nail-segmentation.onnx`, the original `onnx-export-report.json`, the approved `dataset-provenance-report.json`, the approved `holdout-lock-report.json`, the aggregate `segmentation-evaluation-report.json`, `model-metadata.json`, `annotation-agreement-report.json`, `size-calibration-report.json`, `accuracy-report.json`, `operational-report.json`, and the generated `model-card.md` in one directory, then run:

```bash
nailsize-release-bundle /approved-release \
  --expected-model-version MODEL_VERSION \
  --expected-model-sha256 MODEL_SHA256 \
  --output /reports/model-release-manifest.json
```

This final gate independently checks exact eleven-file contents, selected-checkpoint and ONNX checksum/version identity, fixed architecture/provider/tensor contracts, exporter-to-metadata parity linkage, the checksum-linked research-only dataset provenance and consent boundary, the approved holdout lock and identifier-free test-set commitment, exact segmentation/accuracy-to-holdout participant and nail counts, segmentation model/checksum/threshold/review linkage, overlap plus boundary metrics and clustered intervals, annotation agreement coverage/reviews/adjudication, physical best-fit size calibration against the exact production chart, every numeric accuracy and operational threshold, study/cohort counts and reviews, and model-card reproducibility. It emits metadata only. Passing it proves the bundle is internally consistent; it does not prove that the submitted study data was representative or honestly collected, so protected human review remains mandatory.

The default CI suite measures coverage for production and dependency-light ML modules; the heavy PyTorch modules are excluded because their optional dependencies are not installed there. Run the `Model Tooling` GitHub Actions workflow after changes to `modeling.py`, `training.py`, the release chain, or their pinned dependencies. It installs the research extra on Linux and executes the real factory/export/release/training tests.

Benchmark the exported candidate inside the exact Cloud Run container/revision before approval:

```bash
nailsize-benchmark /models/nail-segmentation.onnx \
  --iterations 200 \
  --warmup-iterations 20 \
  --output /reports/onnx-benchmark.json
```

The report includes the model checksum, ONNX Runtime provider, iteration counts, p50/p95/p99/mean latency, logical CPU count, machine/platform, and Python version. This command is useful for candidate and local harness checks. During deployment, Terraform also creates a single-task Cloud Run job from the exact digest-pinned inference image; the workflow runs `python -m app.runtime_benchmark`, verifies the live job and execution metadata plus its single structured log, and retains an aggregate report. A laptop, generic CI run, or Terraform source test does not satisfy the deployment benchmark task—only the credentialed 2-vCPU/4-GiB execution for the released image does.
