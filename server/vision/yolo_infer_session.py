from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import cv2
from ultralytics import YOLO


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run YOLO driver detector on a session or image directory and save yolo_raw.csv"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session", type=str, help="Session folder with frames.csv and frames/*.jpg")
    group.add_argument("--image-dir", type=str, help="Directory containing images")

    parser.add_argument("--weights", type=str, required=True, help="YOLO weights path, e.g. best.pt")
    parser.add_argument("--out", type=str, required=True, help="Output CSV path")
    parser.add_argument("--session-id", type=str, default=None)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--debug-dir", type=str, default=None)
    parser.add_argument("--debug-limit", type=int, default=30)

    return parser.parse_args()


def collect_images_from_dir(image_dir: Path) -> List[Dict[str, str]]:
    paths = sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS)

    rows = []
    for i, p in enumerate(paths, start=1):
        rows.append(
            {
                "frame_id": p.stem,
                "image_path": str(p),
                "display_path": p.name,
            }
        )
    return rows


def collect_images_from_session(session_dir: Path) -> List[Dict[str, str]]:
    frames_csv = session_dir / "frames.csv"

    if frames_csv.exists():
        rows = []
        with frames_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                frame_id = str(row.get("frame_id", i))
                image_rel = row.get("image_path", "")
                image_path = session_dir / image_rel

                rows.append(
                    {
                        "frame_id": frame_id,
                        "image_path": str(image_path),
                        "display_path": image_rel,
                    }
                )
        return rows

    frames_dir = session_dir / "frames"
    if frames_dir.exists():
        return collect_images_from_dir(frames_dir)

    return collect_images_from_dir(session_dir)


def draw_debug(image_bgr, detections):
    out = image_bgr.copy()

    if not detections:
        cv2.putText(
            out,
            "no driver",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        return out

    for det in detections:
        x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
        conf = det["confidence"]

        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(
            out,
            f"driver {conf:.2f}",
            (x1, max(20, y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return out


def main():
    args = parse_args()

    if args.session:
        input_root = Path(args.session)
        items = collect_images_from_session(input_root)
        session_id = args.session_id or input_root.name
    else:
        input_root = Path(args.image_dir)
        items = collect_images_from_dir(input_root)
        session_id = args.session_id or input_root.name

    if not items:
        raise FileNotFoundError(f"No images found: {input_root}")

    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights not found: {weights_path}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    debug_dir = Path(args.debug_dir) if args.debug_dir else None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(weights_path))

    fieldnames = [
        "session_id",
        "frame_id",
        "image_path",
        "class",
        "class_id",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
    ]

    total = len(items)
    detected_frames = 0
    total_detections = 0
    debug_saved = 0

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, item in enumerate(items, start=1):
            image_path = Path(item["image_path"])
            frame_id = item["frame_id"]
            display_path = item["display_path"]

            image_bgr = cv2.imread(str(image_path))
            if image_bgr is None:
                print(f"[WARN] failed to read: {image_path}")
                continue

            result = model.predict(
                source=str(image_path),
                conf=args.conf,
                imgsz=args.imgsz,
                verbose=False,
            )[0]

            detections = []

            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    class_id = int(box.cls[0].item())
                    class_name = result.names.get(class_id, str(class_id))

                    if class_name != "driver":
                        continue

                    conf = float(box.conf[0].item())
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    det = {
                        "session_id": session_id,
                        "frame_id": frame_id,
                        "image_path": display_path,
                        "class": class_name,
                        "class_id": class_id,
                        "confidence": round(conf, 6),
                        "x1": int(round(x1)),
                        "y1": int(round(y1)),
                        "x2": int(round(x2)),
                        "y2": int(round(y2)),
                    }

                    detections.append(det)
                    writer.writerow(det)

            if detections:
                detected_frames += 1
                total_detections += len(detections)

            if debug_dir and debug_saved < args.debug_limit:
                debug_img = draw_debug(image_bgr, detections)
                debug_name = f"{Path(display_path).stem}_yolo.jpg"
                cv2.imwrite(str(debug_dir / debug_name), debug_img)
                debug_saved += 1

            if idx % 50 == 0 or idx == total:
                print(f"[PROGRESS] {idx}/{total}")

    print("")
    print(f"[DONE] output csv: {out_path}")
    print(f"[DONE] total images: {total}")
    print(f"[DONE] detected frames: {detected_frames}")
    print(f"[DONE] total detections: {total_detections}")

    if total > 0:
        print(f"[DONE] detected frame ratio: {detected_frames / total * 100:.1f}%")

    if debug_dir:
        print(f"[DONE] debug images: {debug_dir}")


if __name__ == "__main__":
    main()