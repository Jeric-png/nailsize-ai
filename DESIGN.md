# Design

## Source of truth

- Status: Active
- Last refreshed: 2026-07-13
- Primary product surfaces: landing, Third Series coin confirmation and preparation, four guided capture pairs, eight-point coin-rim calibration, nail-edge marking, repeatability review, results, and recoverable errors.
- Evidence reviewed: Stitch project `8073142126445672722` and its eight approved visual/style references, the implemented React/CSS component system, `PRD.md`, and the approved dataset-free guided-sizing decision.

## Brand

- Personality: clinical, objective, precise, calm, and trustworthy.
- Trust signals: explicit calibration requirements, visible user-confirmed markers, two-photo agreement, plain privacy language, and honest retake instructions.
- Avoid: beauty-editor styling, gradients, decorative shadows, rounded cards, medical claims, or implied certainty.

## Product goals

- Goals: help customers make repeatable, calibrated projected-width measurements without a nail-training dataset or remote image processing, then give nail artists those widths and press-on size recommendations.
- Non-goals: diagnosis, accounts, saved history, ecommerce, or permanent photo storage.
- Success signals: users complete two measurements for each of four capture groups, resolve inconsistent readings, and can copy a ten-nail text summary.

## Personas and jobs

- Primary personas: press-on nail customers and nail artists receiving measurements.
- User jobs: capture safely, understand image requirements, obtain honest measurements, and share results without photos.
- Key contexts: mobile camera use at home with a current Third Series Singapore 50-cent coin; desktop review by nail artists.

## Information architecture

- Primary navigation: one linear sizing task with explicit back, retake, reset, and cancel actions.
- Core routes/screens: `/`, `/prepare`, `/capture/:captureType`, `/guide/:captureType/:sample`, `/results`, and terminal recovery states.
- Content hierarchy: current action, capture/sample progress, calibration or marking instruction, local-processing/privacy statement, primary action, secondary correction.

## Design principles

- Calibration before sizing: never produce millimetres until the supported coin identity, all eight rim markers, and both nail edges have been explicitly confirmed.
- Repetition before recommendation: never accept a capture group when its two readings exceed the documented agreement tolerance.
- Recovery over blame: every rejection names the fix and preserves other completed capture groups.
- Data minimization is visible: explain that photos remain in browser memory and are never uploaded.
- Tradeoffs: error clarity and accessibility take precedence over pixel-level Stitch fidelity.

## Visual language

- Color: charcoal `#1A202C`, background `#F7FAFC`, white surfaces, border `#CBD5E0`, text `#181C1E`, muted text `#45474C`, error `#BA1A1A`.
- Typography: Inter; optional Courier Prime for technical metadata.
- Spacing/layout rhythm: 8px grid, 16px mobile margins, 24px desktop gutters, 1280px maximum width.
- Shape/radius/elevation: square corners, 1px structural borders, 2px priority/focus borders, no shadows.
- Motion: restrained progress feedback; honor reduced motion.
- Imagery/iconography: structural hand/coin placement guides, numbered coin-rim markers, and line icons with text labels. Coin instructions must name the Port of Singapore and large `50`/`CENTS` identifiers; do not rely on color alone.

## Components

- Existing components to reuse: `Button`, `Card`, `Eyebrow`, `ProgressStepper`, and `StatusMessage` primitives plus the shared application shell.
- Guided components: capture frame, `AnnotationSurface`, eight adjustable coin-rim handles, nail-edge controls, repeatability table, measurement row, and error callout.
- Variants and states: primary/secondary/destructive; empty/calibrating/marking/repeat-required/consistent/inconsistent/error/disabled.
- Token/component ownership: CSS custom properties in `apps/web/src/styles/tokens.css`; React primitives in `apps/web/src/components`.

## Accessibility

- Target standard: WCAG 2.2 AA.
- Keyboard/focus behavior: complete keyboard operation and a visible 2px focus ring.
- Contrast/readability: minimum 4.5:1 for text; status never uses color alone.
- Screen-reader semantics: one page heading, labelled capture controls, named calibration/edge handles, live status announcements, and descriptive errors.
- Reduced motion and sensory considerations: no required animation, vibration, or color-only instruction.

## Responsive behavior

- Supported breakpoints/devices: 390px mobile baseline and fluid desktop through 1280px; supported browsers follow `outputs/plan.md`.
- Layout adaptations: four-column mobile flow; twelve-column desktop results with measurements beside the summary.
- Touch/hover differences: minimum 44px touch targets; hover is enhancement only.

## Interaction states

- Loading: local photo preparation is named and announced; no artificial AI-processing state.
- Empty: capture frame explains the required hand, coin placement, and sample number.
- Error: actionable local photo replacement, coin-rim/edge correction, or targeted retake recovery.
- Success: a capture group is accepted only after two locally computed readings agree.
- Disabled: action explains the missing prerequisite.
- Offline/slow network: the complete sizing flow remains functional because measurement is local.

## Content voice

- Tone: direct, supportive, factual, and non-medical.
- Terminology: “projected nail width,” “50-cent reference,” “coin rim,” “first measurement,” “verification measurement,” “agreement,” and “recommended press-on size.”
- Microcopy rules: explain why, give one concrete correction, and never promise perfect fit.

## Implementation constraints

- Framework/styling system: React, TypeScript, Vite, and plain CSS variables.
- Design-token constraints: implement the Clinical Wireframe System without a parallel theme abstraction.
- Performance constraints: normalize photos locally, release object URLs immediately when replaced/reset, and keep pointer/keyboard marker adjustment responsive.
- Compatibility constraints: Vercel-hosted static frontend with no inference API, image upload, model artifact, database, or required runtime secret.
- Test/screenshot expectations: 390px and 1280px Playwright baselines compared with the listed Stitch screens.

## Open questions

- [ ] Product owner: approve final consumer-facing name before public launch; impacts branding only.
- [ ] Nail technician: approve default chart and result terminology before field validation; impacts sizing copy and validation.
- [ ] Nail technician: confirm whether each supported blank chart is measured by projected chord width or curved surface width; highly curved nails remain a manual-review case.
