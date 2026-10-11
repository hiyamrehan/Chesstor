"""Tracker configuration. Every threshold lives here so experiments can freeze and archive it."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml


@dataclass
class TrackerConfig:
    # frame gating
    q_min: float = 0.5               # frames below this quality have no authority (T04)
    unusable_ratio: float = 0.5      # >50% occluded -> frame unusable for state update (spec s.16)
    # temporal buffer (spec s.12)
    buffer_seconds: float = 2.0
    min_stable_frames: int = 8
    stable_post_seconds: float = 0.4
    stable_tolerance: int = 1        # squares allowed to disagree between window halves
    change_threshold: int = 2        # confident square changes that start a TRANSITION (T05)
    medium_confidence: float = 0.70
    # transition scoring / confirmation (spec s.14-15)
    margin: float = 2.5              # nats between best and runner-up hypothesis
    max_unexplained: int = 5         # frozen after dev-seed tuning (seeds 110-113); see report Ch.7
    unexplained_nats: float = 1.5
    unexplained_penalty: float = 1.0  # extra margin (nats) required per unexplained confident square
    transition_timeout: float = 6.0
    uncertain_timeout: float = 8.0   # UNCERTAIN this long -> MANUAL_CORRECTION
    recovery_depth: int = 2          # 2 = also consider a missed ply when 1-ply fails
    # ablation switches (spec s.24)
    use_temporal: bool = True
    use_legal: bool = True
    use_mask: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> TrackerConfig:
        data = yaml.safe_load(Path(path).read_text()) or {}
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)
