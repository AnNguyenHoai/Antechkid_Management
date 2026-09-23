# UI-PROD-10 — Visual Regression & UAT UI

## Goal
Freeze the production UI baseline after UI-PROD-09 and make future visual regressions reviewable without turning font rasterization or DPI differences into noisy CI failures.

## Validation model
UI-PROD-10 deliberately separates two responsibilities:

1. **Automated visual regression** renders real Design System V2 / shell widgets in Qt offscreen on the Windows pytest runner. CI compares semantic state and geometry invariants against a checked-in baseline, rejects blank/catastrophic renders, and uploads the rendered PNGs for inspection.
2. **Physical UI UAT** is executed in the packaged Windows application. A human verifies readability, hierarchy, interaction feedback, permissions, overflow, focus, scaling, and window restore behavior. Each required scenario records one PNG screenshot and is validated by a fail-closed evidence verifier.

Pixel-perfect screenshot hashes are intentionally not a CI gate. Font hinting, display scale, Qt patch level, and Windows rendering can change individual pixels without changing product quality. The semantic baseline is the machine gate; screenshots are the visual evidence.

## Automated visual baseline
Baseline: `tests/visual_baselines/ui_prod_10_gallery.json`.

The gallery renders three production states at 1280×720:
- `read`: READ mode, readonly banner, no active feedback.
- `write_saved`: WRITE mode, editing banner, canonical success feedback.
- `error`: READ mode with application-level error feedback.

The gate protects:
- application top-bar minimum height and state text;
- workspace header minimum height and hierarchy;
- READ/WRITE action visibility;
- feedback visibility;
- form, badge, detail, state and action component composition;
- non-empty/non-flat rendering through sampled color diversity;
- generated PNG evidence for every state.

CI uploads `visual-regression-artifacts/ui_prod_10/` even when pytest fails, so a reviewer can inspect the last rendered state.

## Physical UAT contract
Use `UI_PROD_10_UAT_CHECKLIST.md` and copy `UI_PROD_10_UAT_EVIDENCE_TEMPLATE.json` into a disposable UAT evidence directory. Do not commit screenshots containing real student data.

Required scenarios:
1. `shell-1366x768`
2. `shell-1920x1080`
3. `shell-scale-125`
4. `student-list-read`
5. `student-list-write`
6. `student-form-validation-save`
7. `student-detail-tabs`
8. `enrollment-confirmation-feedback`
9. `loading-empty-error-permission`
10. `window-restore-overflow-focus`

Final verification must bind the evidence to the **exact release candidate** being accepted:

```powershell
python scripts/verify_ui_uat.py path\to\evidence.json `
  --expected-source-commit <EXACT_40_CHAR_RELEASE_SHA> `
  --expected-build-version <EXACT_RELEASE_VERSION>
```

The verifier fails unless all ten scenario IDs appear exactly once, all are `PASS`, required resolution/scale checks are satisfied, every screenshot is a real in-directory PNG suitable for review, and the evidence `source_commit` / `build_version` exactly match the expected release values supplied by the operator.

A structurally valid evidence file from a different build is therefore not acceptable release evidence.

## Defect handling
A physical UAT failure is not hidden by updating the baseline. Classify it first as environment/data issue, intentional approved visual change, or production defect. A production defect gets a separate fix plus a regression test. An intentional UI change updates the baseline only in the same reviewed PR that explains the visual change.

## Scope boundaries
- no service, repository, schema, permission or collaboration behavior changes;
- no workspace redesign;
- no screenshot containing production/student data is committed;
- no pixel-perfect hash gate;
- no claim that offscreen CI replaces physical Windows UAT.

## Definition of Done
- automated gallery renders all three states and emits reviewable PNG evidence;
- semantic baseline tests pass on Windows CI;
- visual evidence artifact is uploaded by the pytest workflow;
- physical UAT checklist and evidence template are explicit;
- evidence verifier is fail-closed, binds evidence to the exact expected source commit/build version, and is regression tested;
- full pytest suite passes.
