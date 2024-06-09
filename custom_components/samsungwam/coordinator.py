"""The Samsung Wireless Audio coordinator."""

from __future__ import annotations
from datetime import datetime, timedelta
import functools

from pywam.lib.exceptions import ApiCallTimeoutError
from pywam.speaker import Speaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    LOGGER,
    MIN_RECONNECTION_INTERVAL,
    PING_INTERVAL,
)


def async_check_response(func):
    """Decorator that check response from speaker.

    Use this to decorate calls to the speaker. If the call is unsuccessful,
    the connection will be reestablished.
    The decorated method must be in a class with a `.coordinator` property,
    containing the SamsungWamCoordinator object for the speaker.
    """

    @functools.wraps(func)
    async def wrapper_check_response(self, *args, **kwargs):
        coordinator: SamsungWamCoordinator = self.coordinator
        try:
            response = await func(self, *args, **kwargs)
        except ConnectionError as exc:
            LOGGER.debug("%s %s", coordinator.id, exc)
            await coordinator.reconnect()
        except ApiCallTimeoutError as exc:
            LOGGER.debug("%s %s", coordinator.id, exc)
            await coordinator.reconnect()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("%s Error sending command to speaker: %s", coordinator.id, exc)
        else:
            return response

    return wrapper_check_response


class SamsungWamCoordinator:
    """Representation of a Samsung Wireless Audio Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.hass = hass
        self.speaker = Speaker(entry.data[CONF_HOST], entry.data[CONF_PORT])
        self._connected: bool = False
        self._last_reconnect_attempt: datetime = datetime.now()
        self._reconnecting: bool = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.unique_id)},  # type: ignore
            manufacturer="Samsung",
            model=self.speaker.attribute.model,
            name=self.speaker.attribute.name,
            sw_version=self.speaker.attribute.software_version,
        )

    @property
    def host(self) -> str:  # type: ignore
        """Return address to speaker."""
        self.entry.data.get(CONF_HOST, "")

    @property
    def id(self) -> str:
        """Returns name and host for speaker."""
        return f"({self.name}@{self.host})"

    @property
    def name(self) -> str:
        """Returns name according to config entry."""
        return self.entry.title

    @property
    def is_connected(self) -> bool:
        """Returns true if coordinator is connected to speaker."""
        return self._connected

    async def connect(self) -> None:
        """Connect to speaker and update attributes."""
        try:
            await self.speaker.connect()
            await self.speaker.update()
        # TODO: Which excemptions should raise ConnectionError?
        # which will cause HA to try to reconnect, and which should
        # reraise causing HA to fail to load integration?
        except Exception as exc:  # pylint: disable=broad-except
            raise ConnectionError(f"{self.id} Could not connect to speaker") from exc

        self.speaker.events.register_subscriber(self.pywam_subscriber)
        self._connected = True

    async def check_connection(self, now=None) -> None:
        """Check if we are connected to speaker."""
        # Check when the latest event was received to decide if we should skip the check
        if datetime.now() -  self.speaker.attribute.last_seen < timedelta(minutes=PING_INTERVAL):
            return
        
        # Send a short request to check connection
        try:
            await self.speaker.get_volume()
        except Exception as exc:
            #TODO: Vilka Exc för reconnect och ska vi berätta för HA att det inte fungerar?
            #Blir den offlin av sig själv i pywam om vi disconnectar?
            await self.reconnect()
        


    async def disconnect(self) -> None:
        """Disconnect and delete speaker from memory."""
        self._connected = False
        self.speaker.events.unregister_subscriber(self.pywam_subscriber)
        try:
            await self.speaker.disconnect()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("%s Error while disconnecting from speaker: %s", self.id, exc)

    async def reconnect(self) -> None:
        """Reconnect to speaker."""
        # Make sure this is not called to often and that it is not
        # called when allready trying to reconnect.
        # TODO: Förklara att denna kallas så fort något anrop misslyckats
        # och det är därför vi måste lägga begärnsningar
        if datetime.now() - self._last_reconnect_attempt < timedelta(minutes=MIN_RECONNECTION_INTERVAL):
            return
        if self._reconnecting:
            return

        self._reconnecting = True
        self._last_reconnect_attempt = datetime.now()
        self._connected = False
        try:
            await self.speaker.disconnect()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("%s Error while reconnecting to speaker: %s", self.id, exc)
        try:
            await self.speaker.connect()
            await self.speaker.update()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("%s Could not connect to speaker", self.id)
        else:
            self._connected = True
        finally:
            self._reconnecting = False

    def pywam_subscriber(self) -> None:
        """Subscriber for state changes from pywam."""
        # If speaker name has change update config entry and device registry.
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
