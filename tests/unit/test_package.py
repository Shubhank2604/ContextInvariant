"""Package import and metadata tests."""

from importlib.resources import files
from pathlib import Path
from tomllib import loads

import contextos


def test_package_version() -> None:
    assert contextos.__version__ == "0.5.0"


def test_public_version_matches_package_metadata() -> None:
    project_root = Path(__file__).parents[2]
    metadata = loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["version"] == contextos.__version__


def test_distribution_declares_inline_type_information() -> None:
    assert files("contextos").joinpath("py.typed").is_file()
