"""Save profiles define consistent output transfer syntax choices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class SaveProfile:
    """Describe a named output profile."""

    identifier: str
    description: str
    transfer_syntax_uid: str
    bits_allocated: int

    @property
    def bits_stored(self) -> int:
        return self.bits_allocated

    @property
    def high_bit(self) -> int:
        return self.bits_allocated - 1


AVAILABLE_PROFILES: Dict[str, SaveProfile] = {
    "ct-implicit-8bit": SaveProfile(
        identifier="ct-implicit-8bit",
        description="CT — Implicit VR, 8-bit",
        transfer_syntax_uid="1.2.840.10008.1.2",
        bits_allocated=8,
    ),
    "ct-explicit-8bit": SaveProfile(
        identifier="ct-explicit-8bit",
        description="CT — Explicit VR, 8-bit",
        transfer_syntax_uid="1.2.840.10008.1.2.1",
        bits_allocated=8,
    ),
}


def get_profile(name: str) -> SaveProfile:
    try:
        return AVAILABLE_PROFILES[name]
    except KeyError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"unknown save profile: {name}") from exc
