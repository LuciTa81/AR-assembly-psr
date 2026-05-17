from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple, Any, List

import cv2
import yaml


DEFAULT_ROI_NAMES = [
    "enclosure",
    "lid",
    "base_front",
    "inner_area",
    "screw_a",
    "screw_b",
    "screw_c",
    "screw_d",
]


Rect = Tuple[int, int, int, int]  # x, y, w, h


def read_image(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")
    return image


def load_layout(layout_path: Path) -> Dict[str, Any]:
    if not layout_path.exists():
        return {
            "layout_version": "roi_layout_v1",
            "image": {
                "width": 800,
                "height": 600,
            },
            "rois": {},
        }

    with layout_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    data.setdefault("layout_version", "roi_layout_v1")
    data.setdefault("image", {})
    data.setdefault("rois", {})

    return data


def save_layout(layout_path: Path, layout: Dict[str, Any]) -> None:
    layout_path.parent.mkdir(parents=True, exist_ok=True)

    with layout_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            layout,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def parse_rect(name: str, value: Any) -> Rect:
    """
    Supports:
    - {x: 10, y: 20, w: 30, h: 40}
    - {x1: 10, y1: 20, x2: 40, y2: 60}
    - [10, 20, 30, 40]  # x, y, w, h
    """
    if isinstance(value, dict):
        if all(k in value for k in ["x", "y", "w", "h"]):
            return (
                int(value["x"]),
                int(value["y"]),
                int(value["w"]),
                int(value["h"]),
            )

        if all(k in value for k in ["x1", "y1", "x2", "y2"]):
            x1 = int(value["x1"])
            y1 = int(value["y1"])
            x2 = int(value["x2"])
            y2 = int(value["y2"])
            return x1, y1, x2 - x1, y2 - y1

    if isinstance(value, (list, tuple)) and len(value) == 4:
        return int(value[0]), int(value[1]), int(value[2]), int(value[3])

    raise ValueError(f"Invalid ROI format for {name}: {value}")


def rect_to_dict(rect: Rect) -> Dict[str, int]:
    x, y, w, h = rect
    return {
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h),
    }


def clamp_rect(rect: Rect, image_width: int, image_height: int) -> Rect:
    x, y, w, h = rect

    x = max(0, min(x, image_width - 1))
    y = max(0, min(y, image_height - 1))

    w = max(1, min(w, image_width - x))
    h = max(1, min(h, image_height - y))

    return x, y, w, h


def draw_overlay(image, rois: Dict[str, Any]):
    overlay = image.copy()
    height, width = overlay.shape[:2]

    for idx, (name, raw_rect) in enumerate(rois.items()):
        rect = parse_rect(name, raw_rect)
        x, y, w, h = clamp_rect(rect, width, height)

        color = (
            int(50 + (idx * 70) % 205),
            int(80 + (idx * 110) % 175),
            int(120 + (idx * 40) % 135),
        )

        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

        label_y = max(20, y - 6)
        cv2.putText(
            overlay,
            name,
            (x, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    return overlay


def crop_rois_from_image(
    image_path: Path,
    layout_path: Path,
    out_dir: Path,
    save_crops: bool = True,
    save_overlay: bool = True,
) -> None:
    image = read_image(image_path)
    image_height, image_width = image.shape[:2]

    layout = load_layout(layout_path)
    rois = layout.get("rois", {})

    if not rois:
        raise ValueError(
            f"No ROIs found in layout: {layout_path}\n"
            f"Run edit mode first:\n"
            f"python server/vision/roi_cropper.py --image {image_path} "
            f"--layout {layout_path} --edit"
        )

    layout_width = layout.get("image", {}).get("width")
    layout_height = layout.get("image", {}).get("height")

    if layout_width != image_width or layout_height != image_height:
        print(
            "[WARN] Layout image size differs from actual image size.\n"
            f"       layout: {layout_width}x{layout_height}\n"
            f"       image : {image_width}x{image_height}\n"
            "       ROI will still be applied as absolute pixel coordinates."
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    if save_crops:
        for name, raw_rect in rois.items():
            rect = parse_rect(name, raw_rect)
            clamped = clamp_rect(rect, image_width, image_height)

            if rect != clamped:
                print(f"[WARN] {name}: clamped {rect} -> {clamped}")

            x, y, w, h = clamped
            crop = image[y : y + h, x : x + w]

            crop_path = out_dir / f"{name}.jpg"
            ok = cv2.imwrite(str(crop_path), crop)

            if not ok:
                raise RuntimeError(f"Failed to save crop: {crop_path}")

            print(f"[OK] crop saved: {crop_path}")

    if save_overlay:
        overlay = draw_overlay(image, rois)
        overlay_path = out_dir / "debug_overlay.jpg"
        ok = cv2.imwrite(str(overlay_path), overlay)

        if not ok:
            raise RuntimeError(f"Failed to save overlay: {overlay_path}")

        print(f"[OK] overlay saved: {overlay_path}")


def edit_layout_on_image(
    image_path: Path,
    layout_path: Path,
    roi_names: List[str],
) -> None:
    image = read_image(image_path)
    image_height, image_width = image.shape[:2]

    layout = load_layout(layout_path)
    layout["layout_version"] = layout.get("layout_version", "roi_layout_v1")
    layout["image"] = {
        "width": int(image_width),
        "height": int(image_height),
    }
    layout.setdefault("rois", {})

    print("")
    print("[INFO] ROI edit mode")
    print("       Drag ROI with mouse.")
    print("       Press ENTER or SPACE to confirm each ROI.")
    print("       Press C or ESC to skip/cancel current ROI.")
    print("")

    for name in roi_names:
        preview = draw_overlay(image, layout["rois"])

        cv2.putText(
            preview,
            f"Select ROI: {name}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        window_name = f"Select ROI - {name}"
        rect = cv2.selectROI(
            window_name,
            preview,
            showCrosshair=True,
            fromCenter=False,
        )
        cv2.destroyWindow(window_name)

        x, y, w, h = [int(v) for v in rect]

        if w <= 0 or h <= 0:
            print(f"[SKIP] {name}")
            continue

        clamped = clamp_rect((x, y, w, h), image_width, image_height)
        layout["rois"][name] = rect_to_dict(clamped)

        save_layout(layout_path, layout)
        print(f"[OK] {name}: {layout['rois'][name]}")
        print(f"     saved layout: {layout_path}")

    final_overlay = draw_overlay(image, layout["rois"])
    debug_path = layout_path.parent / "roi_layout_debug_overlay.jpg"
    cv2.imwrite(str(debug_path), final_overlay)

    print("")
    print(f"[DONE] layout saved: {layout_path}")
    print(f"[DONE] debug overlay saved: {debug_path}")


def collect_images(input_dir: Path) -> List[Path]:
    exts = ["*.jpg", "*.jpeg", "*.png", "*.bmp"]
    paths: List[Path] = []

    for ext in exts:
        paths.extend(input_dir.glob(ext))

    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(
        description="ROI editor/cropper for warped top-view assembly images."
    )

    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Single warped image path, e.g. outputs/warped/000040_warped.jpg",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Directory containing warped images.",
    )
    parser.add_argument(
        "--layout",
        type=str,
        required=True,
        help="ROI layout YAML path, e.g. configs/roi_layout_v1.yaml",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="outputs/roi_crops",
        help="Output directory.",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Interactively select ROIs and save layout YAML.",
    )
    parser.add_argument(
        "--roi-names",
        nargs="+",
        default=DEFAULT_ROI_NAMES,
        help="ROI names to edit in order.",
    )
    parser.add_argument(
        "--no-crops",
        action="store_true",
        help="Do not save ROI crop images.",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="Do not save debug overlay image.",
    )

    args = parser.parse_args()

    layout_path = Path(args.layout)
    out_dir = Path(args.out)

    if args.edit:
        if args.image is None:
            raise ValueError("--edit mode requires --image")
        edit_layout_on_image(
            image_path=Path(args.image),
            layout_path=layout_path,
            roi_names=args.roi_names,
        )
        return

    if args.image is None and args.input_dir is None:
        raise ValueError("Use either --image or --input-dir")

    if args.image is not None:
        image_path = Path(args.image)
        crop_rois_from_image(
            image_path=image_path,
            layout_path=layout_path,
            out_dir=out_dir,
            save_crops=not args.no_crops,
            save_overlay=not args.no_overlay,
        )
        return

    input_dir = Path(args.input_dir)
    image_paths = collect_images(input_dir)

    if not image_paths:
        raise FileNotFoundError(f"No images found in {input_dir}")

    for image_path in image_paths:
        per_image_out = out_dir / image_path.stem
        print("")
        print(f"[PROCESS] {image_path}")
        crop_rois_from_image(
            image_path=image_path,
            layout_path=layout_path,
            out_dir=per_image_out,
            save_crops=not args.no_crops,
            save_overlay=not args.no_overlay,
        )


if __name__ == "__main__":
    main()