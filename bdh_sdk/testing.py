"""Test helpers for hub apps.

Nothing here imports Django at module import time.
"""
import json
import os
import subprocess
import sys

__all__ = ["PluginImportError", "assert_plugin_importable", "probe_plugin_import"]

DEFAULT_FORBIDDEN = ("requests",)

_PROBE = r"""
import json, sys, threading

opts = json.loads(sys.argv[1])
module, app, attr = opts["module"], opts["app"], opts["attr"]
before_threads = {t.ident for t in threading.enumerate()}
before_modules = set(sys.modules)

import importlib
spec = getattr(importlib.import_module(module), attr, None)

new_modules = set(sys.modules) - before_modules
names = opts["forbidden"]
forbidden = sorted(
    m for m in new_modules
    if any(m == n or m.startswith(n + ".") for n in names)
    or m in {app + ".models", app + ".views", app + ".homepage"}
    or m.endswith(".models")
)
apps_ready = False
if "django.apps" in sys.modules:
    apps_ready = sys.modules["django.apps"].apps.ready
settings_configured = False
if "django.conf" in sys.modules:
    settings_configured = sys.modules["django.conf"].settings.configured
print(json.dumps({
    "spec_type": type(spec).__name__,
    "forbidden": forbidden,
    "new_threads": [t.name for t in threading.enumerate() if t.ident not in before_threads],
    "apps_ready": apps_ready,
    "settings_configured": settings_configured,
}))
"""


class PluginImportError(AssertionError):
    """Importing a plugin module had side effects or produced no spec."""


def probe_plugin_import(module_path, *, app=None, attr="spec", forbidden=(),
                        path=(), cwd=None, timeout=60):
    """Import ``module_path`` in a fresh interpreter and report what happened.

    Returns a dict with ``spec_type``, ``forbidden`` (newly imported modules
    that a plugin module must not pull in), ``new_threads``, ``apps_ready``
    and ``settings_configured``. The child sees the caller's ``sys.path``
    plus ``path``; ``DJANGO_SETTINGS_MODULE`` is removed from its environment.
    """
    if app is None:
        app = module_path.split(".")[0]
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    search = [os.fspath(p) for p in path] + [p for p in sys.path if p]
    if env.get("PYTHONPATH"):
        search.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(search)
    opts = {
        "module": module_path,
        "app": app,
        "attr": attr,
        "forbidden": [*DEFAULT_FORBIDDEN, *forbidden],
    }
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(opts)],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise PluginImportError(
            f"importing {module_path} failed:\n{proc.stderr.strip()}"
        )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def assert_plugin_importable(module_path, **kwargs):
    """Assert ``module_path`` exposes a PluginSpec and imports cleanly.

    Importing a plugin module must not set up Django or configure settings,
    start threads, or import ``requests`` or the app's ``models``, ``views``
    or ``homepage`` modules (any ``*.models`` module counts). Pass
    ``forbidden=("name", ...)`` to ban more modules (a name also bans its
    submodules). Other keyword arguments go to :func:`probe_plugin_import`.
    Raises :class:`PluginImportError` (an ``AssertionError``) on failure and
    returns the probe result otherwise.
    """
    result = probe_plugin_import(module_path, **kwargs)
    problems = []
    attr = kwargs.get("attr", "spec")
    if result["spec_type"] != "PluginSpec":
        problems.append(f"{attr} is {result['spec_type']}, expected PluginSpec")
    if result["forbidden"]:
        problems.append(f"imported forbidden modules: {result['forbidden']}")
    if result["new_threads"]:
        problems.append(f"started threads: {result['new_threads']}")
    if result["apps_ready"]:
        problems.append("set up Django (apps registry is ready)")
    if result["settings_configured"]:
        problems.append("configured Django settings")
    if problems:
        raise PluginImportError(
            f"{module_path} is not a clean plugin module: " + "; ".join(problems)
        )
    return result
