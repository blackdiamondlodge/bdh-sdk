import shutil
import tempfile
import textwrap
import unittest
from importlib.util import find_spec
from pathlib import Path

from bdh_sdk.testing import PluginImportError, assert_plugin_importable

SPEC = "from bdh_sdk import PluginSpec\nspec = PluginSpec(id={app!r}, app={app!r})\n"

APPS = {
    "cleanapp": "import json\n" + SPEC,
    "threadapp": textwrap.dedent("""
        import threading
        threading.Thread(target=threading.Event().wait, name="poller", daemon=True).start()
    """) + SPEC,
    "reqapp": "import requests\n" + SPEC,
    "modelsapp": "from . import models\n" + SPEC,
    "heavyapp": "import bdhfake_heavy.sub\n" + SPEC,
    "nospecapp": "spec = None\n",
    "brokenapp": "raise RuntimeError('boom')\n",
    "djangoapp": "import django\nfrom django.conf import settings\nsettings.configure()\n"
                 "django.setup()\n" + SPEC,
}


class AssertPluginImportableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Scratch packages live next to the tests, not in the system temp dir.
        cls.root = Path(tempfile.mkdtemp(prefix="_scratch_", dir=Path(__file__).parent))
        for app, source in APPS.items():
            pkg = cls.root / app
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "models.py").write_text("")
            (pkg / "plugin.py").write_text(source.format(app=app))
        # Stubs so the tests don't depend on what is installed.
        (cls.root / "requests.py").write_text("")
        (cls.root / "bdhfake_heavy").mkdir()
        (cls.root / "bdhfake_heavy" / "__init__.py").write_text("")
        (cls.root / "bdhfake_heavy" / "sub.py").write_text("")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def check(self, app, **kwargs):
        return assert_plugin_importable(f"{app}.plugin", path=[self.root], **kwargs)

    def assertFails(self, app, message, **kwargs):
        with self.assertRaises(PluginImportError) as cm:
            self.check(app, **kwargs)
        self.assertIn(message, str(cm.exception))

    def test_clean_module_passes(self):
        result = self.check("cleanapp")
        self.assertEqual(result["spec_type"], "PluginSpec")
        self.assertEqual(result["forbidden"], [])

    def test_starting_a_thread_fails(self):
        self.assertFails("threadapp", "poller")

    def test_importing_requests_fails(self):
        self.assertFails("reqapp", "requests")

    def test_importing_models_fails(self):
        self.assertFails("modelsapp", "modelsapp.models")

    def test_extra_forbidden_modules(self):
        self.check("heavyapp")
        self.assertFails("heavyapp", "bdhfake_heavy.sub", forbidden=("bdhfake_heavy",))

    def test_missing_spec_fails(self):
        self.assertFails("nospecapp", "expected PluginSpec")

    def test_import_error_fails(self):
        self.assertFails("brokenapp", "boom")

    @unittest.skipIf(find_spec("django") is None, "Django not installed")
    def test_django_setup_fails(self):
        self.assertFails("djangoapp", "set up Django")


if __name__ == "__main__":
    unittest.main()
