"""Provides diagnostics for Samsung Wireless Audio integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from pywam.lib import api_call

from . import WamConfigEntry
from .const import DOMAIN
from .wam_coordinator import SamsungWamCoordinator
from .wam_device import SamsungWamDevice


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: WamConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    # Get all devices that has media players
    coordinator: SamsungWamCoordinator = hass.data[DOMAIN]
    all_devices = {}
    for _, media_player in coordinator.get_all_available_media_players():
        all_devices[media_player.name] = media_player.speaker.attribute._spkmodelname

    # Get the device info
    wam_device = entry.runtime_data.device
    ssdp_data = await _get_ssdp_data(hass, wam_device.speaker.ip)
    api_data = await _get_api_data(wam_device)
    wam_attributes = wam_device.speaker.attribute._get_int_state_copy()
    media_player_properties = wam_device.speaker.attribute.get_state_copy()

    return {
        "device": device.dict_repr,
        "config entry": str(entry),
        "config data": str(entry.data),
        "all_devices": all_devices,
        "ssdp_data": ssdp_data,
        "api_data": api_data,
        "wam_attributes": wam_attributes,
        "media_player_properties": media_player_properties,
    }


async def _get_api_data(wam_device: SamsungWamDevice) -> str:
    """Get API data."""
    resp = await wam_device.speaker.client.request(api_call.get_main_info())
    return str(resp)


async def _get_ssdp_data(hass: HomeAssistant, speaker_ip: str) -> str:
    """Get ssdp data."""
    session = async_get_clientsession(hass)
    async with session.get(f"http://{speaker_ip}:7676/smp_3_") as resp:
        return await resp.text()
