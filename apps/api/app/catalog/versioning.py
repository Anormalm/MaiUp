from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionPolicy:
    ordered_versions: tuple[str, ...]
    current_version: str
    b15_version_count: int = 2

    def __post_init__(self) -> None:
        if self.current_version not in self.ordered_versions:
            raise ValueError(f"Current version is absent from catalog: {self.current_version}")
        if self.b15_version_count < 1:
            raise ValueError("b15_version_count must be positive")

    @property
    def b15_versions(self) -> tuple[str, ...]:
        current_index = self.ordered_versions.index(self.current_version)
        start = max(0, current_index - self.b15_version_count + 1)
        return self.ordered_versions[start : current_index + 1]

    def bucket_for(self, chart_version: str, *, rating_eligible: bool = True) -> str | None:
        if not rating_eligible or chart_version not in self.ordered_versions:
            return None
        chart_index = self.ordered_versions.index(chart_version)
        current_index = self.ordered_versions.index(self.current_version)
        if chart_index > current_index:
            return None
        return "b15" if chart_version in self.b15_versions else "b35"
