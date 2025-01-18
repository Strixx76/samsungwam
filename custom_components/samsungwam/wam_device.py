"""The Samsung Wireless Audio device."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import (
    datetime,
    timedelta,
)
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from pywam.speaker import Speaker

from .const import (
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from . import WamConfigEntry
    from .wam_coordinator import SamsungWamCoordinator


PING_INTERVAL = 60  # Interval to check speaker connection in minutes
GROUPING_ATTRIBUTES = {
    "is_grouped",
    "is_master",
    "is_slave",
    "group_name",
    "master_ip",
    "master_mac",
}


class WamEntityCallback(Protocol):
    """Protocol for typing callbacks."""

    def __call__(self, attributes: dict[str, Any], force_update: bool = False) -> None:
        """Callable."""


class SamsungWamDevice:
    """Samsung Wireless Audio device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WamConfigEntry,
        coordinator: SamsungWamCoordinator,
    ) -> None:
        """Initialize the device."""
        self.entry = entry
        self.coordinator = coordinator
        self.hass = hass
        self.speaker = Speaker(entry.data[CONF_HOST], entry.data[CONF_PORT])
        self._update_callbacks: set[WamEntityCallback] = set()
        self._host = entry.data.get(CONF_HOST, "")
        self._checking_connection: bool = False
        self._reconnecting: bool = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        # TODO: Add model_id=self.speaker.attribute._modelname
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.unique_id)},  # type: ignore
            manufacturer="Samsung",
            model=self.speaker.attribute.model,
            name=self.speaker.attribute.name,
            sw_version=self.speaker.attribute.software_version,
        )

    @property
    def host(self) -> str:
        """Return address to speaker."""
        return self._host

    @property
    def id(self) -> str:
        """Returns name and host for speaker."""
        return f"({self.name}@{self.host})"

    @property
    def is_connected(self) -> bool:
        """Returns true if device is connected."""
        return self.speaker.is_connected

    @property
    def name(self) -> str:
        """Returns name according to config entry."""
        return self.entry.title

    async def _reconnect_until_connected(self) -> None:
        """Try reconnect to speaker until connection is established."""

        self._reconnecting = True
        reconnection_attempts = 0

        while True:
            LOGGER.debug("%s Trying to reconnect", self.id)
            with contextlib.suppress(Exception):
                await self.speaker.disconnect()
                await self.speaker.connect()
                await self.speaker.update()

            if self.is_connected:
                LOGGER.warning("%s Connection to speaker restored", self.id)
                self.update_all_entity_states()
                self.coordinator.update_hass_states()
                self._reconnecting = False
                return

            reconnection_attempts += 1
            # We will wait 20, 40, 80, 160, 320 and max 640 seconds.
            wait_time = 2 ** (min(reconnection_attempts, 6)) * 10
            await asyncio.sleep(wait_time)

    async def check_connection(self) -> None:
        """Check if we are connected to speaker."""
        if self._checking_connection:
            return
        self._checking_connection = True

        LOGGER.debug("%s Checking connection", self.id)
        try:
            await self.speaker.get_volume()
        except Exception:
            # TODO: Should we limit which exceptions that calls reconnect?
            await self.connection_lost()

        self._checking_connection = False

    async def periodic_connection_check(self, time) -> None:
        """Check connection if it is time for it.

        The listener is passed the time it fires in UTC time.
        """
        LOGGER.debug("%s Checking if connection should be checked", self.id)
        if self._checking_connection:
            LOGGER.debug("%s Connection check already running", self.id)
            return
        if self._reconnecting:
            LOGGER.debug("%s Already trying to reconnect to speaker", self.id)
            return
        if self.speaker.attribute.last_seen is None:
            LOGGER.debug("%s Speaker has no attributes", self.id)
            return

        time_since_last_seen = datetime.now() - self.speaker.attribute.last_seen
        skip_time = timedelta(minutes=PING_INTERVAL + 1)
        if time_since_last_seen < skip_time:
            LOGGER.debug(
                "%s Speaker has been seen - No connection check needed", self.id
            )
            return

        await self.check_connection()

    async def connection_lost(self) -> None:
        """Lost connection is discovered."""
        if self._reconnecting:
            return
        LOGGER.warning("%s Connection to speaker lost", self.id)
        self.update_all_entity_states()
        self.coordinator.update_hass_states()
        await self._reconnect_until_connected()

    async def connect(self) -> None:
        """Connect to speaker and update attributes."""
        try:
            await self.speaker.connect()
            await self.speaker.update()
        except Exception as exc:
            LOGGER.exception("Could not connect to speaker: %s", self.id)
            raise ConnectionError(f"{self.id} Could not connect to speaker") from exc

    async def disconnect(self) -> None:
        """Disconnect from speaker."""
        try:
            await self.speaker.disconnect()
        except Exception as exc:
            LOGGER.debug("%s Error while disconnecting from speaker: %s", self.id, exc)

    @callback
    def pywam_subscriber(self, attributes: dict[str, Any]) -> None:
        """Receive state changes from pywam."""

        # Update all entities.
        for update_callback in self._update_callbacks:
            update_callback(attributes)

        # If a speakers grouping attribute changes all media players
        # needs to be updated.
        if GROUPING_ATTRIBUTES.intersection(attributes.keys()):
            self.coordinator.update_hass_states()

        # If speaker name has change update config entry and device registry.
        if "name" not in attributes:
            return
        if self.speaker.attribute.name != self.entry.title:
            # Don't change title if name doesn't exist.
            if not self.speaker.attribute.name:
                return
            self.hass.config_entries.async_update_entry(
                entry=self.entry, title=self.speaker.attribute.name
            )
            # Update device registry
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(
                {(DOMAIN, self.entry.unique_id)}  # type: ignore
            )
            assert device_entry
            device_registry.async_update_device(
                device_entry.id, name=self.speaker.attribute.name
            )

    @callback
    def add_update_callback(self, update_callback: WamEntityCallback) -> None:
        """Add a entity update callback to the device."""
        self._update_callbacks.add(update_callback)

    @callback
    def remove_update_callback(self, update_callback: WamEntityCallback) -> None:
        """Delete a entity update callback from the device."""
        self._update_callbacks.discard(update_callback)

    @callback
    def update_all_entity_states(self) -> None:
        """Update the HASS state for all device entities."""
        for update_callback in self._update_callbacks:
            update_callback(attributes={}, force_update=True)
