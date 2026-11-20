# Pamphlet algorithm verification v7

## Change

- Replaced only the Algorithm figure: eight native shapes and nine connectors became one high-resolution logo-based architecture image.
- Kept the school template, title, advisor/developer fields, all native body text, Tool section, B-stage dashboard and AR example unchanged.
- Saved an editable standalone SVG, HTML preview and 2580 x 2400 PNG.

## Checks performed

- Playwright rendered the figure with local Noto Sans KR. Text bounds and pairwise text-overlap checks: zero failures.
- Minimum diagram type is 40 px, equivalent to 9.02 pt at the 194 pt placed width.
- Inspected the standalone diagram visually: logos and labels are legible, arrow branches align, and no text is clipped.
- Read Google Slides immediately before mutation and supplied requiredRevisionId. New revision: ckdMHYFS_c1Wjw.
- Compared every non-Algorithm page element before/after, ignoring only temporary image content URLs: 24 preserved elements, zero unrelated changes.
- Native issue checker: zero errors, one generic narrative-font warning. The unchanged 9.5 pt body intentionally follows the school's 9-10 pt specification.
- Exported the native deck to PDF and rendered the complete one-page file directly with PDFium. Visual inspection confirmed Algorithm fits its assigned section without clipping, distortion or interference with other content.
- Native page size remains 182 x 257 mm. Google PDF export reports 515 x 728 pt, matching the earlier export rounding.

## Content integrity

- HMM/Viterbi recognition and FSM guidance remain distinct branches; no unsupported live HMM-to-FSM connection was added.
- Existing official/dev-tool logo assets were reused; no fabricated deployment components or new performance claims were added.
- The existing AR image remains labeled as a guidance example. The B dashboard remains the unchanged real UI rendered from the previously documented saved record and photo.
- No camera, Unity runtime, recognition code, calibration, sharing permissions or email submission was changed.

## Deliverables

- Google Slides: https://docs.google.com/presentation/d/1qC8l7l7BlV9nFjRDZPSFTSPoWGQ4czql0V0j303O6Ns/edit
- algorithm-architecture-v7.svg
- algorithm-architecture-v7.png
- C011207_최민준_팜플렛_v7.pdf
- pamphlet-v7-review.png
