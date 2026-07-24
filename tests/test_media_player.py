"""Media-player behaviour tests for the `fix/volume-level-zero` branch.

Builds a ``SamsungWamPlayer`` directly on top of a mocked device/speaker
(no hass, no network) and asserts the volume_level fix:

  * volume_level at 0 -> 0.0 (this branch) vs None (master)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.samsungwam.media_player import SamsungWamPlayer


def make_player(*, volume=0, sound_mode_names=("Standard", "Music", "Clear Voice")):
    """Construct a SamsungWamPlayer wired to a mocked device + speaker."""
    def _mode(mode_name):
        # NB: MagicMock(name=...) sets the mock's repr name, not a .name
        # attribute -- so assign .name explicitly after construction.
        m = MagicMock()
        m.name = mode_name
        return m

    speaker = MagicMock()
    speaker.attribute.volume = volume
    speaker.attribute.sound_mode_list = [_mode(n) for n in sound_mode_names]
    speaker.select_sound_mode = AsyncMock()

    device = MagicMock()
    device.speaker = speaker
    device.entry.unique_id = TEST_UNIQUE_ID
    device.id = "(Living Room@192.168.1.55)"

    player = SamsungWamPlayer(device)
    # entity_id is normally assigned by the platform; set it for property/error use.
    player.entity_id = "media_player.living_room_speaker"
    return player


TEST_UNIQUE_ID = "AABBCCDDEEFF"


# ---------------------------------------------------------------------------
# volume_level when the speaker reports volume == 0
# ---------------------------------------------------------------------------
def test_volume_level_zero_is_reported() -> None:
    """A real volume of 0 must be surfaced as 0.0, not swallowed as None.

    this branch uses ``is not None`` -> 0.0.
    master uses a truthiness check -> 0 is falsy -> None (the bug).
    """
    player = make_player(volume=0)
    assert player.volume_level == 0.0


def test_volume_level_nonzero_unaffected() -> None:
    """Sanity: a normal volume still scales to 0..1 (passes on both branches)."""
    player = make_player(volume=50)
    assert player.volume_level == 0.5
