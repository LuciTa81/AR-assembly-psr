from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract MediaPipe index fingertip coordinates from images or a Quest session."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--image-dir",
        type=str,
        help="Directory containing images, e.g. datasets/driver_yolo_v1/train/images",
    )
    group.add_argument(
        "--session",
        type=str,
        help="Session directory containing frames.csv and frames/*.jpg",
    )

    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output CSV path, e.g. outputs/mediapipe/session_001_mediapipe_raw.csv",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Optional session id. Defaults to folder name.",
    )
    parser.add_argument(
        "--debug-dir",
        type=str,
        default=None,
        help="Optional directory for debug overlay images.",
    )
    parser.add_argument(
        "--debug-limit",
        type=int,
        default=30,
        help="Number of debug overlay images to save.",
    )
    parser.add_argument(
        "--max-num-hands",
        type=int,
        default=2,
        help="Maximum number of hands to detect.",
    )
    parser.add_argument(
        "--min-detection-confidence",
        type=float,
        default=0.5,
        help="MediaPipe min_detection_confidence.",
    )
    parser.add_argument(
        "--min-tracking-confidence",
        type=float,
        default=0.5,
        help="MediaPipe min_tracking_confidence.",
    )

    return parser.parse_args()


def collect_images_from_dir(image_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    image_paths = sorted(
        p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS
    )

    for idx, path in enumerate(image_paths, start=1):
        frame_id = path.stem if path.stem else f"{idx:06d}"
        rows.append(
            {
                "frame_id": frame_id,
                "image_path": str(path),
                "display_path": path.name,
            }
        )

    return rows


def collect_images_from_session(session_dir: Path) -> List[Dict[str, str]]:
    frames_csv = session_dir / "frames.csv"

    if frames_csv.exists():
        rows: List[Dict[str, str]] = []
        with frames_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                frame_id = row.get("frame_id", str(i))
                image_rel = row.get("image_path", "")
                image_path = session_dir / image_rel

                rows.append(
                    {
                        "frame_id": str(frame_id),
                        "image_path": str(image_path),
                        "display_path": image_rel,
                    }
                )
        return rows

    frames_dir = session_dir / "frames"
    if not frames_dir.exists():
        raise FileNotFoundError(f"No frames.csv or frames directory found: {session_dir}")

    return collect_images_from_dir(frames_dir)


def choose_best_hand(
    hand_landmarks_list,
    handedness_list,
    image_width: int,
    image_height: int,
) -> Optional[Dict[str, object]]:
    """
    If multiple hands are detected, choose the hand with the largest landmark bbox area.
    This is a simple heuristic for the working hand.
    """
    if not hand_landmarks_list:
        return None

    best = None
    best_area = -1.0

    for idx, landmarks in enumerate(hand_landmarks_list):
        xs = [lm.x for lm in landmarks.landmark]
        ys = [lm.y for lm in landmarks.landmark]

        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)

        label = "Unknown"
        score = 0.0

        if handedness_list and idx < len(handedness_list):
            cls = handedness_list[idx].classification[0]
            label = cls.label
            score = float(cls.score)

        if area > best_area:
            best_area = area
            best = {
                "landmarks": landmarks,
                "handedness": label,
                "hand_score": score,
                "area": area,
            }

    return best


def landmark_to_pixel(landmark, width: int, height: int) -> Tuple[int, int]:
    x = int(round(landmark.x * width))
    y = int(round(landmark.y * height))

    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))

    return x, y


def draw_debug(
    image_bgr,
    best_hand: Optional[Dict[str, object]],
    index_xy: Tuple[int, int],
    wrist_xy: Tuple[int, int],
):
    out = image_bgr.copy()

    if best_hand is None:
        cv2.putText(
            out,
            "hand_visible=0",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        return out

    ix, iy = index_xy
    wx, wy = wrist_xy

    cv2.circle(out, (ix, iy), 9, (0, 255, 255), -1)
    cv2.circle(out, (wx, wy), 7, (255, 0, 255), -1)

    cv2.putText(
        out,
        f"index_tip=({ix},{iy})",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        out,
        "wrist",
        (wx + 8, wy),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 0, 255),
        2,
        cv2.LINE_AA,
    )

    return out


def main() -> None:
    args = parse_args()

    if args.image_dir:
        input_root = Path(args.image_dir)
        items = collect_images_from_dir(input_root)
        session_id = args.session_id or input_root.name
    else:
        input_root = Path(args.session)
        items = collect_images_from_session(input_root)
        session_id = args.session_id or input_root.name

    if not items:
        raise FileNotFoundError(f"No images found: {input_root}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    debug_dir = Path(args.debug_dir) if args.debug_dir else None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    mp_hands = mp.solutions.hands
    index_tip_id = mp_hands.HandLandmark.INDEX_FINGER_TIP.value
    wrist_id = mp_hands.HandLandmark.WRIST.value

    fieldnames = [
        "session_id",
        "frame_id",
        "image_path",
        "hand_visible",
        "num_hands",
        "handedness",
        "hand_score",
        "index_x",
        "index_y",
        "index_z_norm",
        "wrist_x",
        "wrist_y",
    ]

    visible_count = 0
    missing_image_count = 0
    debug_saved = 0

    with mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=args.max_num_hands,
        min_detection_confidence=args.min_detection_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
    ) as hands, out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        total = len(items)

        for idx, item in enumerate(items, start=1):
            image_path = Path(item["image_path"])
            display_path = item["display_path"]
            frame_id = item["frame_id"]

            image_bgr = cv2.imread(str(image_path))

            if image_bgr is None:
                missing_image_count += 1
                writer.writerow(
                    {
                        "session_id": session_id,
                        "frame_id": frame_id,
                        "image_path": display_path,
                        "hand_visible": 0,
                        "num_hands": 0,
                        "handedness": "None",
                        "hand_score": 0.0,
                        "index_x": -1,
                        "index_y": -1,
                        "index_z_norm": 0.0,
                        "wrist_x": -1,
                        "wrist_y": -1,
                    }
                )
                print(f"[WARN] failed to read image: {image_path}")
                continue

            height, width = image_bgr.shape[:2]
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

            result = hands.process(image_rgb)

            hand_landmarks_list = result.multi_hand_landmarks or []
            handedness_list = result.multi_handedness or []
            num_hands = len(hand_landmarks_list)

            best_hand = choose_best_hand(
                hand_landmarks_list=hand_landmarks_list,
                handedness_list=handedness_list,
                image_width=width,
                image_height=height,
            )

            if best_hand is None:
                row = {
                    "session_id": session_id,
                    "frame_id": frame_id,
                    "image_path": display_path,
                    "hand_visible": 0,
                    "num_hands": 0,
                    "handedness": "None",
                    "hand_score": 0.0,
                    "index_x": -1,
                    "index_y": -1,
                    "index_z_norm": 0.0,
                    "wrist_x": -1,
                    "wrist_y": -1,
                }

                if debug_dir and debug_saved < args.debug_limit:
                    debug_img = draw_debug(image_bgr, None, (-1, -1), (-1, -1))
                    cv2.imwrite(str(debug_dir / f"{Path(display_path).stem}_mp.jpg"), debug_img)
                    debug_saved += 1
            else:
                landmarks = best_hand["landmarks"].landmark

                index_lm = landmarks[index_tip_id]
                wrist_lm = landmarks[wrist_id]

                index_x, index_y = landmark_to_pixel(index_lm, width, height)
                wrist_x, wrist_y = landmark_to_pixel(wrist_lm, width, height)

                visible_count += 1

                row = {
                    "session_id": session_id,
                    "frame_id": frame_id,
                    "image_path": display_path,
                    "hand_visible": 1,
                    "num_hands": num_hands,
                    "handedness": best_hand["handedness"],
                    "hand_score": round(float(best_hand["hand_score"]), 6),
                    "index_x": index_x,
                    "index_y": index_y,
                    "index_z_norm": round(float(index_lm.z), 6),
                    "wrist_x": wrist_x,
                    "wrist_y": wrist_y,
                }

                if debug_dir and debug_saved < args.debug_limit:
                    debug_img = draw_debug(
                        image_bgr,
                        best_hand,
                        (index_x, index_y),
                        (wrist_x, wrist_y),
                    )
                    cv2.imwrite(str(debug_dir / f"{Path(display_path).stem}_mp.jpg"), debug_img)
                    debug_saved += 1

            writer.writerow(row)

            if idx % 50 == 0 or idx == total:
                print(f"[PROGRESS] {idx}/{total}")

    print("")
    print(f"[DONE] output csv: {out_path}")
    print(f"[DONE] total images: {len(items)}")
    print(f"[DONE] hand visible: {visible_count}")
    print(f"[DONE] missing images: {missing_image_count}")

    if len(items) > 0:
        ratio = visible_count / len(items) * 100.0
        print(f"[DONE] hand visible ratio: {ratio:.1f}%")

    if debug_dir:
        print(f"[DONE] debug images: {debug_dir}")


if __name__ == "__main__":
    main()