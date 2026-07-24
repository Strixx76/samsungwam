"""Config-flow tests for the `feature/configurable-wam-port` branch.

Covers the Bronze "config-flow-test-coverage" surface plus the custom
port field this branch adds to the ``user`` step:

  * happy path            -> coverage (passes on both branches)
  * ssdp + already-config -> coverage (passes on both branches)
  * custom port field     -> port stored (this branch) vs no port field (master)

The pywam ``Speaker`` used inside the flow is fully mocked, so no real
speaker/network is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_MODEL_NAME,
    SsdpServiceInfo,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsungwam.const import DOMAIN

SPEAKER_MODULE = "custom_components.samsungwam.config_flow.Speaker"
SETUP_ENTRY = "custom_components.samsungwam.async_setup_entry"

TEST_HOST = "192.168.1.55"
TEST_NAME = "Living Room Speaker"
TEST_MODEL = "SPK-WAM550"
TEST_ID = "AABBCCDDEEFF"


def make_speaker(*, name=TEST_NAME, model=TEST_MODEL, speaker_id=TEST_ID, fail=False):
    """Return a mock that stands in for ``pywam.speaker.Speaker(host, port)``.

    The flow uses ``async with Speaker(host, port) as speaker``, so the object
    returned by calling ``Speaker(...)`` must be an async context manager whose
    ``__aenter__`` yields the mocked speaker.
    """
    speaker = MagicMock()
    speaker.get_name = AsyncMock(return_value=name)
    speaker.get_model = AsyncMock(return_value=model)
    speaker.get_speaker_id = AsyncMock(return_value=speaker_id)
    speaker.update = AsyncMock(
        side_effect=Exception("cannot connect") if fail else None
    )

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=speaker)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# user happy path -> creates a config entry (coverage; both branches)
# ---------------------------------------------------------------------------
async def test_user_happy_path_creates_entry(hass: HomeAssistant) -> None:
    """Valid host -> confirm -> config entry with the expected data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(SPEAKER_MODULE, return_value=make_speaker()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"][CONF_HOST] == TEST_HOST
    assert result["data"][CONF_MODEL] == TEST_MODEL
    assert result["result"].unique_id == TEST_ID


# ---------------------------------------------------------------------------
# ssdp discovery -> confirm form (coverage; both branches)
# ---------------------------------------------------------------------------
async def test_ssdp_discovery_shows_confirm(hass: HomeAssistant) -> None:
    """A supported SSDP model validates and advances to the confirm step."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:wam::urn:samsung.com:service:MultiScreenService:1",
        ssdp_st="urn:samsung.com:service:MultiScreenService:1",
        ssdp_location=f"http://{TEST_HOST}:7676/smp_2_",
        upnp={ATTR_UPNP_MODEL_NAME: TEST_MODEL},
    )

    with patch(SPEAKER_MODULE, return_value=make_speaker()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


# ---------------------------------------------------------------------------
# already-configured abort (coverage; both branches)
# ---------------------------------------------------------------------------
async def test_user_already_configured_aborts(hass: HomeAssistant) -> None:
    """A speaker whose serial already has an entry aborts as already_configured."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ID,
        data={CONF_HOST: "192.168.1.99", CONF_MODEL: TEST_MODEL, CONF_PORT: 55001},
        title=TEST_NAME,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(SPEAKER_MODULE, return_value=make_speaker()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# user step accepts a custom port and stores it (this branch).
#     master has no CONF_PORT field -> submitting it never yields an entry
#     carrying port 56001, so this FAILS on master.
# ---------------------------------------------------------------------------
async def test_user_custom_port_is_stored(hass: HomeAssistant) -> None:
    """A non-default port supplied on the user form ends up in the entry data."""
    custom_port = 56001

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(SPEAKER_MODULE, return_value=make_speaker()) as speaker_factory:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: custom_port}
        )
        # The custom port must actually be used when connecting.
        speaker_factory.assert_called_once_with(TEST_HOST, custom_port)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == custom_port
