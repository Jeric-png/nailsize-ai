# Data and Physical Validation Protocol

## Active release has no nail dataset

`guided-sg50-coin-v1` does not train, fine-tune, or run a nail-recognition model. It therefore requires no nail image dataset, segmentation masks, annotation pipeline, OpenAI key, or Hugging Face account. Users confirm a current Third Series Singapore 50-cent coin and provide coin-rim and nail-edge markers at runtime; selected photos never leave browser memory.

The `ml/` tooling, model manifests, annotation schemas, and older ISO ID-1 study design are retained legacy research work. They are not inputs to the active build, CI, Vercel deployment, or size result.

## Production-data prohibition

Production photos, filenames, metadata, marker coordinates, measurements, and summaries must not be collected for training, analytics, support, or debugging. The application has no ingestion path. A future data-collection feature would require a separate product decision, explicit opt-in research consent, retention/deletion policy, access controls, and privacy/security review before implementation.

Repository image fixtures must be synthetic or separately consented, anonymized, and approved for source control. Fixtures may verify decoders and user flows; they are not evidence of real-world measurement accuracy.

## Physical validation is not model training

The deterministic method can run without a dataset, but claims about millimetre accuracy or press-on fit still require empirical testing. Such testing is a validation study, not a training corpus. Validation observations must never be fed back into the active algorithm without a versioned product decision.

An approved validation protocol should:

1. use the production Third Series 50-cent coin, four-capture, two-photo flow;
2. include varied in-tolerance coins, real devices, coin placement, lighting, nail widths, and nail curvature;
3. record the two browser readings and their repeat difference before revealing ground truth;
4. have trained nail professionals independently establish widest projected width with a calibrated physical instrument;
5. test actual tip coverage using the exact artist/manufacturer tip set and lot, without compression;
6. adjudicate technician disagreement without exposing the browser suggestion; and
7. report aggregate error, repeatability, rejection/missingness, chart agreement, device results, and curvature-stratified results.

Study photos and direct identifiers stay in a separately approved research location, never in Git or application telemetry. Publish only aggregate evidence that cannot identify a participant. Predetermine the sample size and acceptance thresholds with a qualified method reviewer; this repository does not invent a participant count or accuracy target.

## Ground-truth interpretation

Physical widest projected width can evaluate the local coin-scale and marker method. It cannot convert a top-down observation into curved surface length. The method also does not perform a full homography or correct arbitrary perspective. Curvature and camera angle must be recorded and analyzed separately. Tip-fit evaluation must use the actual physical chart; the provisional `platform-default@1` mapping (size 0 at 18 mm through size 9 at 9 mm) is not ground truth.

Until that study passes, describe outputs only as guided projected widths and provisional size suggestions. Do not claim validated accuracy, model confidence, personalized fit, or guaranteed fit.
