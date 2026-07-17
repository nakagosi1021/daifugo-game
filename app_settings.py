from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from rules import RuleSettings


DIFFICULTY_LABELS: dict[str, str] = {
    "easy": "かんたん",
    "normal": "ふつう",
    "hard": "むずかしい",
}


@dataclass(slots=True)
class AppSettings:
    cpu_count: int = 3
    cpu_difficulty: str = "normal"
    demo_mode: bool = False
    rules: RuleSettings = field(
        default_factory=lambda: RuleSettings.from_preset("standard")
    )
    standard_rules: RuleSettings = field(
        default_factory=lambda: RuleSettings.from_preset("standard")
    )

    def __post_init__(self) -> None:
        self.cpu_count = min(3, max(1, int(self.cpu_count)))
        if self.cpu_difficulty not in DIFFICULTY_LABELS:
            self.cpu_difficulty = "normal"

    @property
    def player_count(self) -> int:
        return self.cpu_count + 1

    def to_dict(self) -> dict[str, object]:
        return {
            "cpu_count": self.cpu_count,
            "cpu_difficulty": self.cpu_difficulty,
            "demo_mode": self.demo_mode,
            "rules": self.rules.to_dict(),
            "standard_rules": self.standard_rules.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AppSettings":
        built_in_standard = RuleSettings.from_preset("standard").to_dict()

        raw_standard_rules = data.get("standard_rules", {})
        if isinstance(raw_standard_rules, dict):
            merged_standard_rules = {
                key: bool(raw_standard_rules.get(key, default_value))
                for key, default_value in built_in_standard.items()
            }
        else:
            merged_standard_rules = built_in_standard.copy()

        raw_rules = data.get("rules", {})
        if isinstance(raw_rules, dict):
            merged_rules = {
                key: bool(raw_rules.get(key, default_value))
                for key, default_value in built_in_standard.items()
            }
        else:
            merged_rules = built_in_standard.copy()

        return cls(
            cpu_count=int(data.get("cpu_count", 3)),
            cpu_difficulty=str(data.get("cpu_difficulty", "normal")),
            demo_mode=bool(data.get("demo_mode", False)),
            rules=RuleSettings(**merged_rules),
            standard_rules=RuleSettings(**merged_standard_rules),
        )


def load_settings(path: Path) -> AppSettings:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return AppSettings()

    if not isinstance(data, dict):
        return AppSettings()

    try:
        return AppSettings.from_dict(data)
    except (TypeError, ValueError):
        return AppSettings()


def save_settings(path: Path, settings: AppSettings) -> None:
    try:
        path.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        # 設定保存に失敗しても、ゲーム自体は続けられるようにする。
        pass
