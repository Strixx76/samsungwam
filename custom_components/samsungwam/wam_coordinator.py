"""The Samsung Wireless Audio coordinator."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers.event import async_call_later
from pywam.lib.exceptions import PywamError

from .const import LOGGER
from .exceptions import WamGroupError

if TYPE_CHECKING:
    from .media_player import SamsungWamPlayer


class SamsungWamCoordinator:
    """Samsung Wireless Audio coordinator.

    Keeps track of all added media players and handle
    grouping of speakers.
    """

    def __init__(self) -> None:
        """Initialize the coordinator."""
        self._media_players: dict[str, SamsungWamPlayer] = {}
        self._grouping_master: str | None = None
        self._grouping_speakers_to_add: list[str] = []
        self._grouping_speakers_to_remove: list[str] = []
        self._grouping_call_later_cancel: CALLBACK_TYPE | None = None
        self._grouping_in_progress: bool = False

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

    def add_speakers_to_group(self, master_id: str, media_players: list[str]) -> None:
        """Add speakers to a master."""
        if self._grouping_in_progress:
            LOGGER.debug("(Coordinator) Grouping operation is already in progress")
            return

        self._validate_master(master_id)
        self._validate_media_players_to_add(master_id, media_players)

        if self._grouping_master is None:
            self._grouping_master = master_id
        elif self._grouping_master != master_id:
            LOGGER.error(
                "(Coordinator) Grouping operation in progress with another master"
            )
            raise WamGroupError()

        self._grouping_speakers_to_add.extend(media_players)

        # Perform the grouping 1 second from now
        if self._grouping_call_later_cancel is not None:
            return
        master = self.get_media_player(master_id)
        self._grouping_call_later_cancel = async_call_later(
            master.hass, 1, self.async_group_media_players
        )

    def remove_speaker_from_group(self, master_id: str, media_player: str) -> None:
        """Add speakers to a master."""
        if self._grouping_in_progress:
            LOGGER.debug("(Coordinator) Grouping operation is already in progress")
            return

        self._validate_master(master_id)
        self._validate_media_player_to_remove(master_id, media_player)

        if self._grouping_master is None:
            self._grouping_master = master_id
        elif self._grouping_master != master_id:
            LOGGER.error(
                "(Coordinator) Grouping operation in progress with another master"
            )
            raise WamGroupError()

        self._grouping_speakers_to_remove.append(media_player)

        # Perform the grouping 1 second from now
        if self._grouping_call_later_cancel is not None:
            return
        master = self.get_media_player(master_id)
        self._grouping_call_later_cancel = async_call_later(
            master.hass, 1, self.async_group_media_players
        )

    async def async_group_media_players(self, now: datetime) -> None:
        """Create or edit a speaker group."""
        if self._grouping_in_progress:
            LOGGER.debug("(Coordinator) Grouping operation is already in progress")
            return
        self._grouping_in_progress = True

        # Start grouping
        try:
            await self._group_wam_speakers()
        except WamGroupError as exc:
            LOGGER.error("(Coordinator) %s", exc)
            raise
        except PywamError as exc:
            LOGGER.error("(pywam) %s", exc)
            raise WamGroupError() from None
        finally:
            # Wait until all speakers have reported new states
            await asyncio.sleep(2)
            # Reset attributes
            self._grouping_master = None
            self._grouping_speakers_to_add = []
            self._grouping_speakers_to_remove = []
            self._grouping_call_later_cancel = None
            self._grouping_in_progress = False
            # Update all media players
            self.update_hass_states()

    async def _group_wam_speakers(self) -> None:
        """Calculate and call pywam grouping."""
        LOGGER.debug("(Coordinator) Master: %s", self._grouping_master)
        master_player = self.get_media_player(self._grouping_master)
        master_speaker = master_player.speaker

        # Slaves before
        if master_player.group_members is not None:
            slaves_before = master_player.group_members[1:]
        else:
            slaves_before = []
        LOGGER.debug("(Coordinator) Slaves before: %s", slaves_before)

        # Slaves after
        LOGGER.debug(
            "(Coordinator) Slaves to remove: %s", self._grouping_speakers_to_remove
        )
        LOGGER.debug("(Coordinator) Slaves to add: %s", self._grouping_speakers_to_add)
        slaves_after = set(slaves_before)
        slaves_after.difference_update(set(self._grouping_speakers_to_remove))
        slaves_after.update(set(self._grouping_speakers_to_add))
        LOGGER.debug("(Coordinator) Slaves after: %s", slaves_after)

        # Call master of the group to perform the grouping
        speakers_before = [self.get_media_player(s).speaker for s in slaves_before]
        speakers_after = [self.get_media_player(s).speaker for s in slaves_after]
        await master_speaker.group(speakers_before, speakers_after)

    def _validate_media_players_to_add(
        self, master_id: str, media_player_ids: list[str]
    ) -> None:
        """Validate media player that should be added to a group."""
        master_player = self.get_media_player(master_id)
        master_speaker = master_player.speaker

        for media_player_id in media_player_ids:
            try:
                player = self.get_media_player(media_player_id)
                speaker = player.speaker
            except KeyError:
                LOGGER.error("%s is not a SamsungWam media player", media_player_id)
                raise WamGroupError() from None
            if not player.available:
                LOGGER.error(
                    "%s Speaker is not available (online) at the moment",
                    player.device.id,
                )
                raise WamGroupError()
            if speaker.attribute.is_master:
                LOGGER.error(
                    "%s Speaker is already a master and can't be grouped",
                    player.device.id,
                )
                raise WamGroupError()
            if player.group_members is not None:
                if master_player.group_members is None:
                    LOGGER.error(
                        "%s Media player is already a slave in another group",
                        player.device.id,
                    )
                    raise WamGroupError()
                elif media_player_id not in master_player.group_members:
                    LOGGER.error(
                        "%s Media player is already a slave in another group",
                        player.device.id,
                    )
                    raise WamGroupError()
            if (
                speaker.attribute.is_slave
                and speaker.attribute.master_ip != master_speaker.ip
            ):
                LOGGER.error(
                    "%s Speaker is already a slave in another group", player.device.id
                )
                raise WamGroupError()

    def _validate_media_player_to_remove(
        self, master_id: str, media_player_id: str
    ) -> None:
        """Validate media player that should be removed from a group."""
        master_player = self.get_media_player(master_id)
        player = self.get_media_player(media_player_id)
        speaker = player.speaker

        if not speaker.attribute.is_slave:
            LOGGER.error("%s Speaker is not part of a group", player.device.id)
            raise WamGroupError()
        if len(player.group_members) == 0:
            LOGGER.error("%s Media player is not part of a group", player.device.id)
            raise WamGroupError()

        if media_player_id not in master_player.group_members:
            LOGGER.error("%s Media player is not part of the group", player.device.id)
            raise WamGroupError()

    def _validate_master(self, media_player_id: str) -> None:
        """Validate master for a speaker group."""
        player = self.get_media_player(media_player_id)
        speaker = player.speaker

        if speaker.attribute.is_slave:
            LOGGER.error(
                "%s Speaker is slave in group and can't become master", player.device.id
            )
            raise WamGroupError()

        if player.group_members is None:
            if speaker.attribute.is_grouped:
                LOGGER.error(
                    "%s Speaker is already grouped and can't become master",
                    player.device.id,
                )
                raise WamGroupError()

        if player.group_members is not None:
            if player.entity_id != player.group_members[0]:
                LOGGER.error(
                    "%s Media player is slave in group and can't become master",
                    player.device.id,
                )
                raise WamGroupError()
            if not speaker.attribute.is_master:
                LOGGER.error("%s Speaker is not master", player.device.id)
                raise WamGroupError()

            for player_slave in player.group_members[1:]:
                speaker_slave = self.get_media_player(player_slave).speaker
                if speaker_slave.attribute.master_ip != speaker.ip:
                    LOGGER.error(
                        "%s Speaker is not slave in this group", player_slave.device.id
                    )
                    raise WamGroupError()
