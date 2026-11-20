import cv2
import numpy as np
import pytest

from server.realtime.roi_realtime import load_image


def test_load_roi_template_from_unicode_path(tmp_path):
    directory = tmp_path / "\ud64d\uc775\ub300" / "\uc870\ub9bd"
    directory.mkdir(parents=True)
    path = directory / "box_present.png"
    expected = np.full((8, 12, 3), [20, 80, 140], dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", expected)
    assert ok
    path.write_bytes(encoded.tobytes())

    np.testing.assert_array_equal(load_image(path), expected)


@pytest.mark.parametrize("content", [b"", b"not an image"])
def test_load_roi_template_rejects_invalid_image(tmp_path, content):
    path = tmp_path / "broken.jpg"
    path.write_bytes(content)

    with pytest.raises(FileNotFoundError, match="failed to read image"):
        load_image(path)
