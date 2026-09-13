"""Guards on the package metadata itself."""

import tomllib
from pathlib import Path

import hanoi_crossing

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    """__version__ and the packaged version drift apart easily; pin them together."""
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert hanoi_crossing.__version__ == declared


def test_engine_has_no_runtime_dependencies() -> None:
    """A zero-dependency runtime is a deliberate security property, so assert it."""
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    assert declared == []
