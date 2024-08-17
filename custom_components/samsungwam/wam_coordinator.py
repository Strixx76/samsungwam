"""The Samsung Wireless Audio coordinator."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from .const import LOGGER

if TYPE_CHECKING:
    from .media_player import SamsungWamPlayer


class SamsungWamCoordinator:
    """Samsung Wireless Audio coordinator.

    Keeps track of all added media players so that we can handle
    grouping of speakers.
    """

    def __init__(self) -> None:
        """Initialize the coordinator."""
        self._media_players: dict[str, SamsungWamPlayer] = {}
        self.grouping_in_progress: bool = False

    def add_media_player(self, entity_id: str, media_player: SamsungWamPlayer) -> None:
        """Add a media player to coordinator."""
        LOGGER.debug("(Coordinator) Adding new media player: %s", entity_id)
        self._media_players[entity_id] = media_player

    def delete_media_player(self, entity_id: str) -> None:
        """Delete a media player."""
        LOGGER.debug("(Coordinator) Deleting media player: %s", entity_id)
        try:
            del self._media_players[entity_id]
        except KeyError:
            LOGGER.error(
                "(Coordinator) Can not delete %s because it was not loaded", entity_id
            )

    def get_media_player(self, entity_id: str) -> SamsungWamPlayer:
        """Return a media_player object."""
        return self._media_players[entity_id]

    def get_all_available_media_players(self) -> Iterator[tuple[str, SamsungWamPlayer]]:
        """Return all stored media players that are online."""
        for entity_id, media_player in self._media_players.items():
            if media_player.available:
                yield entity_id, media_player

    def update_hass_states(self) -> None:
        """Update hass states for all media players that are online.

        Must be called after all speakers are added to hass to get
        correct grouping information.
        """
        for _, media_player in self.get_all_available_media_players():
            media_player.async_write_ha_state()
