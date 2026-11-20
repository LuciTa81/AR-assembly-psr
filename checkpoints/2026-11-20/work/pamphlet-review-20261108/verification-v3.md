# V3 Verification

- Current native slide p contains the school template background, a deterministic original-photo/Unity-UI composite, and an actual supervisor UI screenshot. The prior AI-generated photo is not present in the slide.
- No image-generation model was used for V3. Node Sharp performed photographic cropping, black-background alpha extraction of Unity UI pixels, proportional scaling/placement, and contrast backplates. No UI words, ring, box, or marker were synthesized.
- Main image is explicitly labeled as a workbench-photo + Unity-UI composite. Editorial positioning is not evidence of measured optical registration. Unity source was the actual application's synthetic-input test capture, not a through-lens photo.
- Supervisor capture uses unmodified supervisor frontend files and actual successful-session record 518. Only replay transport source/clock fields change to allow display; the observation and state are from the saved record. No camera or unrelated photograph is inserted into that capture. Visible pamphlet caption labels it as recorded-log playback.
- Source SHA-256 hashes, extraction rectangles, UI locations, replay source and screenshot crop are in visual-provenance-v3.json. build-real-visuals-v3.cjs reproduces the assets.
- Browser assertions passed: correct S2 / screw A / OBSERVED state, stored-session source label, zero page errors, zero frame.jpg camera preview requests. Browser closed normally.
- Native issue checker found no errors; 9-10pt school-template body fonts create two generic small-font warnings.
- Initial PDF review found the supervisor screenshot overlapping the second Development line. One consolidated repair moved the screenshot and cropped only empty UI space. Final one-page PDF was rendered and visually inspected: no text/image overlaps or clipped text, both image aspect ratios preserved, no AI caption or generated asset remains.
- Final PDF: C011207_최민준_v3.pdf. Native readback: raw-output-v3-final.json.
- Existing export caveat persists: native advisor/developer are Noto Sans KR 11pt weight600; Google PDF export had emitted Regular. No claim that this font-export issue is resolved.
- No camera capture, AR runtime changes, calibration changes, sharing changes or submission/email actions.
