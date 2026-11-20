import importlib.util
import unittest


class PixelMappingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pick_A'), 'A picker is not implemented yet')
        from pick_A import raw_pixel, marker_pixel
        self.raw_pixel = raw_pixel
        self.marker_pixel = marker_pixel
        self.crop = (400,305,490,390)

    def test_enlarged_pixels_map_to_original_pixel(self):
        for x,y,expected in [(0,0,[400,305]),(7,7,[400,305]),(8,8,[401,306]),(719,679,[489,389])]:
            self.assertEqual(self.raw_pixel(x,y,self.crop),expected)

    def test_outside_click_is_ignored(self):
        for x,y in [(-1,0),(0,-1),(720,0),(0,680)]:
            self.assertIsNone(self.raw_pixel(x,y,self.crop))

    def test_marker_returns_to_selected_pixel(self):
        for point in ([400,305],[440,340],[489,389]):
            x,y = self.marker_pixel(point,self.crop)
            self.assertEqual(self.raw_pixel(x,y,self.crop),point)


if __name__=='__main__':
    unittest.main()
