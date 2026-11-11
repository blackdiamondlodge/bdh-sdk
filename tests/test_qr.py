import unittest
import xml.etree.ElementTree as ET
from importlib.util import find_spec

SVG = "{http://www.w3.org/2000/svg}"


@unittest.skipUnless(find_spec("qrcode"), "needs the qr extra")
class QrSvgTests(unittest.TestCase):
    def test_well_formed_with_monogram(self):
        from bdh_sdk.qr import qr_svg

        root = ET.fromstring(qr_svg("http://hub.local/upload/abc"))
        logos = [e for e in root.iter(f"{SVG}svg") if e.get("class") == "qr-logo"]
        self.assertEqual(len(logos), 1)
        self.assertTrue(list(logos[0]), "monogram content should be inlined")

    def test_logo_hole_is_clear_of_dots(self):
        from bdh_sdk.qr import qr_svg

        root = ET.fromstring(qr_svg("x" * 120))
        logo = next(e for e in root.iter(f"{SVG}svg") if e.get("class") == "qr-logo")
        x0, y0 = float(logo.get("x")), float(logo.get("y"))
        x1, y1 = x0 + float(logo.get("width")), y0 + float(logo.get("height"))
        for dot in root.iter(f"{SVG}circle"):
            cx, cy = float(dot.get("cx")), float(dot.get("cy"))
            self.assertFalse(x0 <= cx <= x1 and y0 <= cy <= y1, (cx, cy))


if __name__ == "__main__":
    unittest.main()
