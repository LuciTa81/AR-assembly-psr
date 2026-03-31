from pathlib import Path
import cv2
import pandas as pd


def replay_session(session_dir: str, delay_ms: int = 200):
    session_dir = Path(session_dir)
    frames_csv = session_dir / "frames.csv"

    if not frames_csv.exists():
        raise FileNotFoundError(f"frames.csv not found in {session_dir}")

    df = pd.read_csv(frames_csv)

    for _, row in df.iterrows():
        img_path = session_dir / row["image_path"]
        img = cv2.imread(str(img_path))

        if img is None:
            print(f"[WARN] Failed to read {img_path}")
            continue

        cv2.imshow("session replay", img)
        key = cv2.waitKey(delay_ms)
        if key == 27:  # ESC
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python server/pipelines/offline_replay.py <session_dir>")
    else:
        replay_session(sys.argv[1])
