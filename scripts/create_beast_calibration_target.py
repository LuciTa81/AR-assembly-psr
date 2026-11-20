"""Generate the vector A4 target. ReportLab is a tooling-only dependency."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def create_target(path: Path) -> None:
    width, height = landscape(A4)
    columns, rows, square = 10, 7, 25 * mm
    left = (width - columns * square) / 2
    bottom = (height - rows * square) / 2
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        page = canvas.Canvas(output, pagesize=(width, height), pageCompression=1)
        page.setTitle("Beast Camera Calibration - A4 - 25 mm")
        page.setAuthor("AR Assembly Project")
        page.setViewerPreference("PrintScaling", "None")
        page.setFillColorRGB(0, 0, 0)
        for row in range(rows):
            for column in range(columns):
                if (row + column) % 2 == 0:
                    page.rect(
                        left + column * square,
                        bottom + row * square,
                        square,
                        square,
                        stroke=0,
                        fill=1,
                    )

        page.setFont("Helvetica-Bold", 9)
        page.drawString(left, 201 * mm, "BEAST CAMERA CALIBRATION")
        page.setFont("Helvetica", 8)
        page.drawRightString(
            width - left, 201 * mm,
            "25 mm squares | 10 x 7 squares | 9 x 6 inner corners",
        )

        # Two physical scale checks detect printer scaling in either axis.
        page.setLineWidth(0.5)
        page.line(left, 12 * mm, left + 100 * mm, 12 * mm)
        for tick in range(11):
            x = left + tick * 10 * mm
            extent = 1.5 * mm if tick in (0, 10) else 0.7 * mm
            page.line(x, 12 * mm - extent, x, 12 * mm + extent)
        page.setFont("Helvetica", 8)
        page.drawCentredString(left + 50 * mm, 6 * mm, "100 mm - measure between end ticks")

        x, y = 283.5 * mm, 55 * mm
        page.line(x, y, x, y + 100 * mm)
        for tick in range(11):
            extent = 1.5 * mm if tick in (0, 10) else 0.7 * mm
            page.line(x - extent, y + tick * 10 * mm, x + extent, y + tick * 10 * mm)
        page.saveState()
        page.translate(289 * mm, 105 * mm)
        page.rotate(90)
        page.drawCentredString(0, 0, "100 mm - measure between end ticks")
        page.restoreState()

        page.setFont("Helvetica-Bold", 8)
        page.drawRightString(width - left, 11 * mm, "A4 LANDSCAPE | ACTUAL SIZE / 100%")
        page.setFont("Helvetica", 7)
        page.drawRightString(width - left, 6 * mm, "No Fit / Shrink. Keep white margins. Mount flat. No lamination.")
        page.showPage()
        page.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    create_target(arguments.out)
    print(arguments.out.resolve())
