"""The package root serves some of its names lazily, and its stub declares them.

The root cannot import the model layer at import time, because Django imports
the package while it is still loading apps. Names that reach the models are
therefore resolved through a module-level __getattr__ and declared in
__init__.pyi, so a type checker sees their real types. These tests hold the
three descriptions of the root together: the runtime __all__, the lazy table,
and the stub.

What guards the eager/lazy split. The static partition test reads the root's
own source and fails if a lazy name is also bound by a plain import. A second
regression, an eager import of a lazy name, also stops pytest before any test
runs: pytest-django calls django.setup() during startup, and that imports the
package. So the startup failure is the loud gate, and the partition test is
the one a reader can run in isolation. The subprocess tests below check what a
fresh interpreter loads, for the cases where the runner is not the first to
import the package.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import django_outbound_webhooks

PACKAGE_DIR = Path(django_outbound_webhooks.__file__).parent
REPO_ROOT = PACKAGE_DIR.parent

# The lazy table is private to the root, so the stub does not declare it and a
# type checker would reject a plain attribute access. Read it from the namespace.
LAZY: dict[str, str] = vars(django_outbound_webhooks)["_LAZY_EXPORTS"]
PUBLIC = set(django_outbound_webhooks.__all__)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _stub_names() -> set[str]:
    """Every name the stub re-exports or declares at top level."""
    names: set[str] = set()
    for node in _parse(PACKAGE_DIR / "__init__.pyi").body:
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname for alias in node.names if alias.asname == alias.name)
    return names


def _stub_all() -> list[str]:
    for node in _parse(PACKAGE_DIR / "__init__.pyi").body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise AssertionError("the stub declares no __all__")


def _eager_names() -> set[str]:
    """Every name the root's own source binds with a plain from-import."""
    names: set[str] = set()
    for node in _parse(PACKAGE_DIR / "__init__.py").body:
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stub_declares_exactly_the_public_names() -> None:
    assert _stub_names() == PUBLIC


def test_stub_all_matches_runtime_all() -> None:
    assert _stub_all() == django_outbound_webhooks.__all__


def test_lazy_table_names_are_public_and_declared_in_the_stub() -> None:
    assert set(LAZY) <= PUBLIC
    assert set(LAZY) <= _stub_names()


def test_every_public_name_is_either_eager_or_lazy_and_never_both() -> None:
    eager = _eager_names()
    assert eager.isdisjoint(LAZY)
    assert eager | set(LAZY) == PUBLIC


def test_importing_the_package_in_a_fresh_interpreter_loads_no_models() -> None:
    """Django imports the package before apps are ready, so the import must stay light.

    After a plain import, none of the lazy leaf modules may be loaded, nor any
    module under the package's models, nor django.db.models, which the eager
    root used to pull in through endpoints_for.
    """
    leaves = sorted(set(LAZY.values()))
    result = _run_python(
        "import sys\n"
        "import django_outbound_webhooks\n"
        f"forbidden = {leaves!r} + ['django.db.models']\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "loaded += [m for m in sys.modules if m.startswith('django_outbound_webhooks.models')]\n"
        "print(loaded)\n"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "[]"


def test_every_lazy_name_resolves_after_setup_in_a_fresh_interpreter() -> None:
    result = _run_python(
        "import django\n"
        "django.setup()\n"
        "import importlib\n"
        "import django_outbound_webhooks as root\n"
        "for name, module_path in root._LAZY_EXPORTS.items():\n"
        "    leaf = getattr(importlib.import_module(module_path), name)\n"
        "    assert getattr(root, name) is leaf, name\n"
        "print('resolved', len(root._LAZY_EXPORTS))\n"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == f"resolved {len(LAZY)}"


@pytest.mark.parametrize("name", sorted(LAZY))
def test_lazy_name_is_the_leaf_module_object(name: str) -> None:
    leaf = importlib.import_module(LAZY[name])
    assert getattr(django_outbound_webhooks, name) is getattr(leaf, name)


def test_lazy_name_is_cached_into_the_package_namespace() -> None:
    name = "register_endpoint"
    getattr(django_outbound_webhooks, name)
    assert name in vars(django_outbound_webhooks)


def test_unknown_attribute_raises_attribute_error() -> None:
    missing = "no_such_name"
    with pytest.raises(AttributeError, match="no attribute 'no_such_name'"):
        getattr(django_outbound_webhooks, missing)


def test_dir_lists_lazy_names_that_were_never_accessed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every lazy name from the namespace first, so only __dir__ can list them.

    Earlier tests cache the lazy names into the module dict, so without this a
    dir() that ignored them would still look complete.
    """
    for name in LAZY:
        monkeypatch.delitem(vars(django_outbound_webhooks), name, raising=False)
    assert set(dir(django_outbound_webhooks)) >= PUBLIC
