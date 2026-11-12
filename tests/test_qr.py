import tempfile
import unittest
import xml.etree.ElementTree as ET
from importlib.util import find_spec
from pathlib import Path
from unittest import mock

from bdh_sdk import branding

SVG = "{http://www.w3.org/2000/svg}"
SITE_LOGO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect id="site" width="100" height="100"/></svg>'


def _logo(root):
    return next(e for e in root.iter(f"{SVG}svg") if e.get("class") == "qr-logo")


class BrandingTests(unittest.TestCase):
    def test_defaults_to_black_diamond_hub(self):
        b = branding.brand()
        self.assertEqual(b["name"], "Black Diamond Hub")
        self.assertEqual(b["subtitle"], "")
        self.assertIn('aria-label="Black Diamond Hub"', branding.monogram_svg())
        self.assertIn('fill="#0b1622"', branding.monogram_svg())  # dark diamond
        self.assertIn('fill="#fff"', branding.monogram_svg(light=True).split("<path")[0])

    def test_site_overrides_with_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "site.svg"
            path.write_text(SITE_LOGO, encoding="utf-8")
            conf = {"name": "Black Diamond Lodge", "subtitle": "Sun Peaks · BC", "monogram": str(path)}
            with mock.patch.object(branding, "_conf", return_value=conf):
                b = branding.brand()
                self.assertEqual((b["name"], b["subtitle"]), ("Black Diamond Lodge", "Sun Peaks · BC"))
                self.assertIn('id="site"', branding.monogram_svg())
                # a key the site leaves out still falls back to the default
                self.assertIn('aria-label="Black Diamond Hub"', branding.monogram_svg(light=True))


@unittest.skipUnless(find_spec("qrcode"), "needs the qr extra")
class QrSvgTests(unittest.TestCase):
    def test_well_formed_with_default_monogram(self):
        from bdh_sdk.qr import qr_svg

        logo = _logo(ET.fromstring(qr_svg("http://hub.local/upload/abc")))
        self.assertTrue(list(logo), "monogram content should be inlined")
        self.assertIn("translate(-1.62 0)", ET.tostring(logo, encoding="unicode"))  # the BDH glyphs

    def test_uses_site_monogram(self):
        from bdh_sdk.qr import qr_svg

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "site.svg"
            path.write_text(SITE_LOGO, encoding="utf-8")
            with mock.patch.object(branding, "_conf", return_value={"monogram": str(path)}):
                svg = qr_svg("hello")
        self.assertIsNotNone(_logo(ET.fromstring(svg)).find(f"{SVG}rect[@id='site']"))

    def test_explicit_logo_wins(self):
        from bdh_sdk.qr import qr_svg

        svg = qr_svg("hello", logo=SITE_LOGO)
        self.assertIsNotNone(_logo(ET.fromstring(svg)).find(f"{SVG}rect[@id='site']"))

    def test_logo_hole_is_clear_of_dots(self):
        from bdh_sdk.qr import qr_svg

        for text in ("x" * 120, "x" * 400):
            with self.subTest(length=len(text)):
                root = ET.fromstring(qr_svg(text))
                logo = _logo(root)
                x0, y0 = float(logo.get("x")), float(logo.get("y"))
                x1, y1 = x0 + float(logo.get("width")), y0 + float(logo.get("height"))
                for dot in root.iter(f"{SVG}circle"):
                    cx, cy = float(dot.get("cx")), float(dot.get("cy"))
                    self.assertFalse(x0 <= cx <= x1 and y0 <= cy <= y1, (cx, cy))

    def test_long_text_uses_low_ecc_and_smaller_logo(self):
        import qrcode

        from bdh_sdk.qr import qr_svg

        text = "x" * 400
        root = ET.fromstring(qr_svg(text))
        n = float(root.get("viewBox").split()[2])
        low = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, border=4)
        low.add_data(text)
        low.make(fit=True)
        self.assertEqual(n, len(low.get_matrix()))
        self.assertLess(float(_logo(root).get("width")) / n, 0.2)


if __name__ == "__main__":
    unittest.main()
