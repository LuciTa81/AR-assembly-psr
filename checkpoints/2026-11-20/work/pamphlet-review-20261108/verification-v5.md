# Pamphlet v5 verification

- Native Google Slides edited in place: `1qC8l7l7BlV9nFjRDZPSFTSPoWGQ4czql0V0j303O6Ns`, slide `p`.
- School template, section geometry and page size (182 x 257 mm) preserved.
- Title: Noto Sans KR, Bold 26 pt. Advisor and developer: SemiBold 11 pt.
- Body and diagram labels: 9-9.5 pt. No auto-shrink. This is the school's explicit body size; the generic 12 pt checker warning is an intentional template exception.
- Official VITURE Beast photo, six technology logos, AR illustration and dashboard retain their aspect ratios.
- Limitations/scope paragraph removed; motivation and implemented workflow retained. The AR figure caption is `AR 작업 안내 예시`.
- HMM/Viterbi and MediaPipe remain a separate dashed analysis path. The live guidance path is represented by FSM.
- First consolidated repair fixed normalized native line transforms, logo spacing, FSM wrapping and dashboard/text spacing.
- Second consolidated repair widened the MediaPipe label. Direct PDFium rendering verifies the full label is on one line.
- Native geometry/font/aspect-ratio assertions pass (`verify-v5.cjs`). Local issue checker: no errors; one template-native font-size warning.
- Final PDF: one page. Whole-page and Tool detail rendered directly from the final PDF and visually inspected. No remaining clipped text, distorted media or out-of-panel connector lines observed.
- Export-and-render helper's canonical Drive PDF export used; its Unix-only file materialization was adapted to Windows PowerShell. Final verification uses direct PDFium rendering to avoid stale wrapper previews.
- Original v4 and all source media preserved. No runtime, calibration, sharing permissions or email submission changed.
