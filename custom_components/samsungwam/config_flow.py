"""Config flow for the Samsung Wireless Audio integration."""

from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
)
from homeassistant.helpers.service_info import ssdp
from pywam.device import SPEAKER_MODELS, get_device_info
from pywam.speaker import Speaker

from .const import (
    DOMAIN,
    LOGGER,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=55001): cv.port,  # type: ignore
    }
)

ERROR_ALREADY_CONFIGURED: Final = "already_configured"
ERROR_ALREADY_IN_PROGRESS: Final = "already_in_progress"
ERROR_CANNOT_CONNECT: Final = "cannot_connect"
ERROR_NO_SERIAL: Final = "no_serial"
ERROR_NOT_SUPPORTED: Final = "not_supported"


class SamsungWamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Samsung multiroom config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.config_data = {}
        self.config_title = ""
        self.config_id = ""

    async def async_validate_device(self, host, port) -> ConfigFlowResult | None:
        """Validate data by fetching speaker attributes."""
        LOGGER.debug("Trying to connect to speaker at: %s", host)

        try:
            async with Speaker(host, port) as speaker:
                name = await speaker.get_name()
                model = await speaker.get_model()
                speaker_id = await speaker.get_speaker_id()

            self.config_data = {
                CONF_HOST: host,
                CONF_MODEL: model,
                CONF_PORT: port,
            }
            self.config_title = name
            self.config_id = speaker_id
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Error while getting speaker data")
            # TODO: Better error handling
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)

        # Unique ID
        if not self.config_id:
            return self.async_abort(reason=ERROR_NO_SERIAL)
        await self.async_set_unique_id(self.config_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.config_data[CONF_HOST]}
        )

        return None

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by ssdp discovery."""
        LOGGER.debug("Samsung multiroom speaker found via SSDP: %s", discovery_info)

        # Upnp data
        host = urlparse(discovery_info.ssdp_location).hostname
        ssdp_model = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME)
        # serial_number = discovery_info.upnp.get(ssdp.ATTR_UPNP_SERIAL)

        # Speaker info from pywam
        if ssdp_model is None or ssdp_model not in SPEAKER_MODELS:
            return self.async_abort(reason=ERROR_NOT_SUPPORTED)
        port = get_device_info(ssdp_model).port

        # Validate speaker
        if result := await self.async_validate_device(host, port):
            return result

        return await self.async_step_confirm()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Validate speaker
            if result := await self.async_validate_device(host, port):
                return result

            # Go to confirmation step if no errors
            if not errors:
                return await self.async_step_confirm()

        # Show input form
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle confirmation for adding device."""

        # Show confirmation form
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "name": self.config_title,
                    "model": self.config_data[CONF_MODEL],
                },
                errors={},
            )

        # Add to registry
        return self.async_create_entry(title=self.config_title, data=self.config_data)
