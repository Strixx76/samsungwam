"""The Samsung Wireless Audio integration."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .wam_coordinator import SamsungWamCoordinator
from .wam_device import (
    PING_INTERVAL,
    SamsungWamDevice,
)

PLATFORMS = [Platform.MEDIA_PLAYER]

type WamConfigEntry = ConfigEntry[WamData]


@dataclass
class WamData:
    """Stores all entry data."""

    device: SamsungWamDevice


async def async_setup_entry(hass: HomeAssistant, entry: WamConfigEntry) -> bool:
    """Set up Samsung Wireless Audio from a config entry."""
    # SamsungWamCoordinator is one per domain and needs to be stored
    # in hass.data.
    hass.data.setdefault(DOMAIN, SamsungWamCoordinator())
    coordinator: SamsungWamCoordinator = hass.data[DOMAIN]

    # Setup device and connect to speaker
    device = SamsungWamDevice(hass, entry, coordinator)
    try:
        await device.connect()
    except Exception as exc:  # pylint: disable=broad-except
        raise ConfigEntryNotReady() from exc
    device.speaker.events.register_subscriber(device.pywam_subscriber, 1)
    entry.runtime_data = WamData(device)

    # Check speaker connection every ping interval
    entry.async_on_unload(
        async_track_time_interval(
            hass, device.periodic_connection_check, timedelta(minutes=PING_INTERVAL)
        )
    )

    # Setup all entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WamConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload all entities
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Unsubscribe to new events and disconnect from speaker.
    device = entry.runtime_data.device
    with contextlib.suppress(Exception):
        device.speaker.events.unregister_subscriber(device.pywam_subscriber)
        await device.disconnect()

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
