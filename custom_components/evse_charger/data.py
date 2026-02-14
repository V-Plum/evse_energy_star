"""Custom types for ha_evse_charger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import EvseEnergyStarCoordinator


type EvseEnergyStarConfigEntry = ConfigEntry[EvseEnergyStarData]


@dataclass
class EvseEnergyStarData:
    """Data for the Evse Energy Star integration."""

    coordinator: EvseEnergyStarCoordinator
    integration: Integration
