"""The Samsung Wireless Audio integration."""

from __future__ import annotations

from pywam.speaker import Speaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    ID_MAPPINGS,
    LOGGER,
    CONF_WAM_DATA,
    CONF_WAM_OPT,
    HASS_WAM_SPEAKER,
)


PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung Wireless Audio from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if ID_MAPPINGS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][ID_MAPPINGS] = {}

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    speaker = Speaker(host, port)

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_WAM_DATA: entry.data,
        CONF_WAM_OPT: entry.options,
        HASS_WAM_SPEAKER: speaker,
    }

    try:
        await speaker.connect()
        await speaker.update()
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Could not connect to speaker: %s at %s", entry.title, host)
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Close connection to speaker
    speaker = hass.data[DOMAIN][entry.entry_id][HASS_WAM_SPEAKER]
    await speaker.client.disconnect()
    # Delete speaker object and remove settings in memory
    del hass.data[DOMAIN][entry.entry_id][HASS_WAM_SPEAKER]
    hass.data[DOMAIN][entry.entry_id] = {}

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
