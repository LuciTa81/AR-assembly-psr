from pathlib import Path
import cv2

def generate_markers(
    output_dir: str = "outputs/aruco_markers",
    dictionary_name: int = cv2.aruco.DICT_4X4_50,
    marker_ids=(0, 1, 2, 3),
    marker_size_px: int = 600,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_name)

    for marker_id in marker_ids:
        marker_img = cv2.aruco.generateImageMarker(
            aruco_dict,
            marker_id,
            marker_size_px
        )

        out_path = output_dir / f"aruco_4x4_id_{marker_id}.png"
        cv2.imwrite(str(out_path), marker_img)
        print(f"Saved: {out_path}")

if __name__ == "__main__":
    generate_markers()