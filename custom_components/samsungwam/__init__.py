"""The Samsung Wireless Audio integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    ID_MAPPINGS,
    COORDINATOR,
    LOGGER,
    PING_INTERVAL,
)
from .coordinator import SamsungWamCoordinator


PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung Wireless Audio from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if ID_MAPPINGS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][ID_MAPPINGS] = {}

    coordinator = SamsungWamCoordinator(hass, entry)

    try:
        await coordinator.connect()
    except ConnectionError as exc:
        raise ConfigEntryNotReady() from exc
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            "%s Exception while trying to connect to speaker", coordinator.id
        )

    hass.data[DOMAIN][entry.entry_id] = {COORDINATOR: coordinator}

    # Check speaker connection every ping interval
    entry.async_on_unload(
        async_track_time_interval(
            hass, coordinator.check_connection, timedelta(minutes=PING_INTERVAL)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator: SamsungWamCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    await coordinator.disconnect()

    hass.data[DOMAIN].pop(entry.entry_id, None)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
