"""Keep narrow white paper borders out of metric ArUco corners."""

from unittest.mock import patch

import cv2
import numpy as np
import pytest

from server.vision.calibrate_marker_layout_v2 import detect_markers


def paper_marker():
    image = np.full((320, 400, 3), 60, np.uint8)
    image[75:185, 115:225] = 255
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, 3, 100)
    image[80:180, 120:220] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return image


@pytest.mark.parametrize('scale', [1., 1.5])
def test_apriltag_refinement_finds_black_boundary_in_original_pixels(scale):
    mapping, corners, ids = detect_markers(paper_marker(), scale, corner_refinement='apriltag')
    expected = np.array([[120, 80], [220, 80], [220, 180], [120, 180]])
    assert ids.flatten().tolist() == [3]
    assert len(corners) == 1
    np.testing.assert_allclose(mapping[3], expected, atol=1.)


def test_default_stays_subpix_for_existing_callers():
    image = paper_marker()
    default, _, default_ids = detect_markers(image, 1.)
    explicit, _, explicit_ids = detect_markers(image, 1., corner_refinement='subpix')
    np.testing.assert_array_equal(default_ids, explicit_ids)
    np.testing.assert_array_equal(default[3], explicit[3])


def test_invalid_refinement_is_not_silently_ignored():
    with pytest.raises(ValueError, match='corner refinement'):
        detect_markers(paper_marker(), 1., corner_refinement='unknown')


def test_requested_apriltag_requires_opencv_support():
    with patch.object(cv2.aruco, 'CORNER_REFINE_APRILTAG', None):
        with pytest.raises(ValueError, match='not available'):
            detect_markers(paper_marker(), 1., corner_refinement='apriltag')
