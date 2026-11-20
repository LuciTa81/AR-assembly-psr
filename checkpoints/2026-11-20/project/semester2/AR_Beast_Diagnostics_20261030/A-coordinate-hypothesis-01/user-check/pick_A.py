"""Pick A in saved photographs. No camera, prediction, or calibration updates."""

import argparse
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from uuid import uuid4

from PIL import Image, ImageDraw, ImageTk


SCALE = 8
ROOT = Path(__file__).resolve().parents[2]
SAMPLES = [
    ("capture-13-A-stationary/frame-000031/raw.png", (400, 305, 490, 390)),
    ("capture-13-A-stationary/frame-000091/raw.png", (530, 275, 620, 360)),
    ("capture-12-A-seated-repeat/frame-000001/raw.png", (535, 425, 625, 510)),
]


def raw_pixel(x, y, crop):
    x0, y0, x1, y1 = crop
    if not (0 <= x < (x1 - x0) * SCALE and 0 <= y < (y1 - y0) * SCALE):
        return None
    return [x0 + int(x // SCALE), y0 + int(y // SCALE)]


def marker_pixel(point, crop):
    return tuple((point[i] - crop[i] + 0.5) * SCALE - 0.5 for i in (0, 1))


def now():
    return datetime.now(timezone.utc).isoformat()


class Picker:
    def __init__(self, window, output):
        from server.realtime.camera_calibration import write_json

        self.write_json = write_json
        self.window = window
        self.output = output / "observations.json"
        self.index = 0
        self.point = None
        self.finished = False
        self.data = {
            "schema": "saved_photo_A_landmarks_v1", "observer": "user",
            "created_at": now(), "status": "in_progress",
            "activation_status": "not_activated", "observations": [],
        }
        self.write_json(self.output, self.data)
        window.title("A center | 1/3")
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self.close)
        panel = ttk.Frame(window, padding=12)
        panel.pack()
        self.title = ttk.Label(panel, font=("Segoe UI", 13))
        self.title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.context = ttk.Label(panel)
        self.context.grid(row=1, column=0, sticky="n", padx=(0, 12))
        self.canvas = tk.Canvas(panel, width=720, height=680, highlightthickness=0)
        self.canvas.grid(row=1, column=1)
        self.canvas.bind("<Button-1>", self.click)
        controls = ttk.Frame(panel)
        controls.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(controls, text="\ub2eb\uae30", command=self.close).pack(side="left", padx=4)
        ttk.Button(controls, text="\uac74\ub108\ub6f0\uae30", command=self.skip).pack(side="left", padx=4)
        self.confirm = ttk.Button(controls, text="\ud655\uc778", command=self.save)
        self.confirm.pack(side="left", padx=4)
        window.bind("<Return>", lambda event: self.save())
        window.bind("<Escape>", lambda event: self.close())
        self.show()

    def show(self):
        name, self.crop = SAMPLES[self.index]
        source = ROOT / name
        payload = source.read_bytes()
        picture = Image.open(io.BytesIO(payload)).convert("RGB")
        if picture.size != (1280, 720):
            raise ValueError(f"Unexpected source dimensions: {source}")
        self.source = {
            "source": str(source), "source_sha256": hashlib.sha256(payload).hexdigest(),
            "source_size": list(picture.size), "crop": list(self.crop), "scale": SCALE,
        }
        context = picture.copy()
        ImageDraw.Draw(context).rectangle(self.crop, outline="#ffcf33", width=4)
        context.thumbnail((320, 180))
        self.context_image = ImageTk.PhotoImage(context)
        self.context.configure(image=self.context_image)
        self.crop_image = ImageTk.PhotoImage(picture.crop(self.crop).resize((720, 680), Image.Resampling.NEAREST))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.crop_image)
        self.point = None
        self.confirm.state(["disabled"])
        self.title.configure(text=f"A \uc911\uc2ec \ud655\uc778 | {self.index + 1}/3 | {name}")
        self.window.title(f"A center | {self.index + 1}/3")
        self.canvas.focus_set()

    def click(self, event):
        point = raw_pixel(event.x, event.y, self.crop)
        if point is None:
            return
        self.point = point
        x, y = marker_pixel(point, self.crop)
        self.canvas.delete("selection")
        self.canvas.create_oval(x - 14, y - 14, x + 14, y + 14,
                                outline="#00ffff", width=2, tags="selection")
        self.confirm.state(["!disabled"])
        self.canvas.focus_set()

    def save(self):
        if self.point is not None:
            self.record("confirmed", self.point.copy())

    def skip(self):
        self.record("unscorable", None)

    def record(self, status, point):
        if self.finished:
            return
        entry = dict(self.source, status=status, raw_pixel=point, confirmed_at=now())
        updated = dict(self.data, observations=self.data["observations"] + [entry])
        last = self.index + 1 == len(SAMPLES)
        if last:
            updated.update(status="completed", finished_at=now())
        try:
            self.write_json(self.output, updated, exclusive=False)
        except OSError as error:
            messagebox.showerror("Save failed", str(error), parent=self.window)
            return
        self.data = updated
        print(f"SAVED {self.index + 1}/3 {status} {point}", flush=True)
        if last:
            self.finished = True
            self.window.destroy()
        else:
            self.index += 1
            self.show()

    def close(self):
        if self.finished:
            return
        updated = dict(self.data, status="partial", finished_at=now())
        try:
            self.write_json(self.output, updated, exclusive=False)
        except OSError as error:
            messagebox.showerror("Save failed", str(error), parent=self.window)
            return
        self.finished = True
        self.window.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(__file__).parent / ("run-" + datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8])
    output.mkdir(exist_ok=False)
    window = tk.Tk()
    picker = Picker(window, output)
    window.update_idletasks()
    window.lift()
    window.attributes("-topmost", True)
    window.after(800, lambda: window.attributes("-topmost", False))
    print(f"READY {picker.output}", flush=True)
    window.mainloop()


if __name__ == "__main__":
    main()
