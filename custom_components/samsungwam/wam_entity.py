"""Mixin for WAM entities."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from pywam.lib.exceptions import ApiCallTimeoutError

from .const import LOGGER

if TYPE_CHECKING:
    from .wam_device import SamsungWamDevice


def async_check_connection(timeout: bool = False):
    """Check connection to speaker.

    Use this to decorate calls to the speaker. If the call is unsuccessful,
    the connection will be checked.
    If timeout is set we will also check on timeouts awaiting the response.
    This should only be used on calls we know all speakers supports.
    """

    def outer_wrapper(func):
        @functools.wraps(func)
        async def inner_wrapper(self, *args, **kwargs):
            device: SamsungWamDevice = self.device
            try:
                response = await func(self, *args, **kwargs)
            except ConnectionError as exc:
                LOGGER.debug("%s %s", device.id, exc)
                await device.check_connection()
            except ApiCallTimeoutError as exc:
                LOGGER.debug("%s %s", device.id, exc)
                if timeout:
                    await device.check_connection()
            except Exception as exc:
                LOGGER.error("%s Error sending command to speaker: %s", device.id, exc)
            else:
                return response

        return inner_wrapper

    return outer_wrapper


class WamEntity(Entity):
    """An WAM entity."""

    _attr_should_poll = False

    def __init__(
        self,
        device: SamsungWamDevice,
    ) -> None:
        """Initialize the WAM entity class."""
        self.device = device
        self.speaker = device.speaker
        self._unique_id = device.entry.unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.is_connected

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return self.device.device_info

    @property
    def wam_monitored_attributes(self) -> set[str] | None:
        """Returns all attributes to monitor.

        If None no attribute changes will trigger an update of the entity.
        If empty list is returned an update will always be triggered.

        To be implemented by the platform entity.
        """
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        To be extended by integrations.

        Called when an entity has their entity_id and hass object
        assigned, before it is written to the state machine for the
        first time. Example uses: restore the state, subscribe to
        updates or set callback/dispatch function/listener.
        """
        await super().async_added_to_hass()
        self.device.add_update_callback(self.wam_updates_from_device)
        await self.wam_async_added_to_hass_extra()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        To be extended by integrations.

        Called when an entity is about to be removed from Home Assistant.
        Example use: disconnect from the server or unsubscribe from
        updates.
        """
        super().async_will_remove_from_hass()
        self.device.remove_update_callback(self.wam_updates_from_device)
        await self.wam_async_will_remove_from_hass_extra()

    async def wam_async_added_to_hass_extra(self) -> None:
        """Run when entity about to be added to hass.

        To be extended by platform.
        """

    async def wam_async_will_remove_from_hass_extra(self) -> None:
        """Run when entity will be removed from hass.

        To be extended by platform.
        """

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated.

        To be extended by integrations.
        """

    async def async_removed_from_registry(self) -> None:
        """Run when entity has been removed from entity registry.

        To be extended by integrations.
        """

    @callback
    def wam_updates_from_device(
        self, attributes: dict[str, Any], force_update: bool = False
    ) -> None:
        """Receives state changes from SamsungWamDevice."""
        if force_update:
            self.async_write_ha_state()
        if self.wam_monitored_attributes is None:
            return
        if not self.wam_monitored_attributes:
            self.async_write_ha_state()
            return
        elif self.wam_monitored_attributes.intersection(attributes.keys()):
            self.async_write_ha_state()
