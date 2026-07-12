# Dataset and Ground-Truth Protocol

## Scope and governance

The development dataset is separate from the production application. Production uploads cannot enter this dataset through any technical path. Study data is collected only after explicit research consent and stored in an access-controlled research location; no participant photos or direct identifiers belong in Git.

Each participant receives a random study identifier. The re-identification key, consent record, compensation record, and contact information are stored separately from images and annotations. Withdrawal requests use the re-identification key and remove eligible source data and future training derivatives according to the approved consent terms.

## Inclusion and exclusion

Include adults who can provide informed consent and complete the four-photo flow with bare, natural nails. Recruit across Fitzpatrick/Monk skin-tone representation, device classes, nail widths, curvature, lengths, and relevant capture environments.

Exclude or label unsupported captures involving polish, artificial nails, opaque decoration, active injury/infection, severe deformity, obscured lateral nail boundaries, missing required digits, a non-planar or flexible reference, or inability to establish reliable physical ground truth. Exclusion is not a medical diagnosis.

## Capture procedure

1. Confirm consent and assign the pseudonymous participant ID.
2. Record only approved cohort fields using coarse categories.
3. Use the production four-capture UI and a blank ISO ID-1 calibration card.
4. Capture left fingers, left thumb, right fingers, and right thumb on at least two supported devices where feasible.
5. Repeat one complete capture set after repositioning to measure repeatability.
6. Record retakes and typed rejection reasons rather than deleting failed attempts.
7. Strip EXIF on research ingestion and retain the minimum metadata required by the approved study.

## Physical measurement

Two trained nail technicians independently measure the widest visible nail-bed width with a calibrated digital instrument. Record the raw reading to 0.1 mm, instrument identifier, calibration date, technician pseudonym, and repeat reading. A third adjudicator resolves readings differing by more than 0.5 mm or any disputed boundary.

The adjudicated value is ground truth for projected-width evaluation. Because planar photography cannot observe full curvature, record curvature cohort separately and do not relabel projected width as surface width.

## Best-fit procedure

Use the exact immutable `platform-default@1` physical tip set. Two technicians independently select the smallest tip that covers the nail without compression and record adjacent/borderline candidates. Disagreement is adjudicated without revealing model output. Record tip lot and chart version.

## Annotation

Annotators label each fingertip crop using `ml/annotations/nail-annotation.schema.json`:

- nail mask and visible lateral boundaries;
- digit and submitted capture type;
- base-to-tip longitudinal axis;
- physical width and best-fit labels;
- capture quality codes and exclusion reason;
- annotation/technician identifiers and schema version.

At least 10% of images are double-annotated. Quality tooling checks required fields, normalized geometry, valid enums, positive physical measurements, and participant split integrity. Report mask Dice, boundary distance, digit agreement, quality-code agreement, width disagreement, and best-fit Cohen’s kappa. IoU/Dice cannot approve a model without boundary and physical metrics.

## Split and lock procedure

Assign train/validation/test using the pseudonymous participant ID, a versioned secret split salt, and the deterministic tooling in `ml/nailsize_ml/dataset.py`. Every image and repeat from one participant must remain in one split. The training manifest uses the exact research-only schema enforced by `dataset_provenance.py`: image and participant pseudonyms, split, relative image and mask paths, dataset version, `approved_research_study` origin, and `active_research_consent` status. Extra fields and any other origin or consent state fail validation.

Before training, generate and independently approve the aggregate-only dataset provenance report. It binds the immutable manifest checksum, dataset version, split counts, participant counts, research approval, and production-exclusion review without exposing participant IDs or paths. Store the exact secret split salt in a protected file outside Git, give that salt version a public identifier, and run `nailsize-holdout-lock` before model selection. The lock revalidates every participant assignment and records only aggregate test counts plus an identifier-free SHA-256 commitment. Independently approve the lock report checksum; training, checkpoints, selected-model exports, and final releases must carry the provenance, manifest, and holdout-lock identities unchanged.

No threshold tuning, architecture selection, or relabeling may use public-release holdout results. Any correction requires a new dataset version, split review, and independently approved lock report. The protected salt, participant pseudonyms, and image pseudonyms must never enter the report or release bundle.

## Required studies

- Feasibility: at least 100 participants and 1,000 nails through the production capture flow.
- Public release: at least 200 participant-disjoint people and 2,000 held-out nails with adjudicated physical ground truth.

Reports must include participant-clustered confidence intervals, capture/rejection flow, missingness, repeatability, device results, and adequately sampled subgroup metrics. The release gates remain those in `outputs/plan.md`; this protocol does not weaken them.
