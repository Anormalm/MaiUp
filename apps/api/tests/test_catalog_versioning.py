import pytest

from app.catalog.versioning import VersionPolicy


def test_current_version_must_exist() -> None:
    with pytest.raises(ValueError, match="absent"):
        VersionPolicy(("A", "B"), "C")


def test_first_version_does_not_underflow_b15_window() -> None:
    policy = VersionPolicy(("A", "B"), "A")
    assert policy.b15_versions == ("A",)
    assert policy.bucket_for("B") is None
