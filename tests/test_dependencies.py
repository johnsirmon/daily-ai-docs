"""Security contracts for dependencies used by networked workflows."""

from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]
CERTIFI_FIXED = Version("2026.10.19")


def _requirements(path: Path) -> dict[str, Requirement]:
    requirements = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            requirement = Requirement(line)
            requirements[requirement.name.lower()] = requirement
    return requirements


def test_certifi_floor_and_lock_exclude_compromised_ca_bundle():
    direct = _requirements(ROOT / "requirements.txt")["certifi"]
    locked = _requirements(ROOT / "requirements.lock")["certifi"]

    assert direct.specifier == SpecifierSet(f">={CERTIFI_FIXED}")
    locked_specifier = next(iter(locked.specifier))
    assert locked_specifier.operator == "=="
    assert Version(locked_specifier.version) >= CERTIFI_FIXED
