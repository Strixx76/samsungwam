"""The Samsung Wireless Audio media player platform."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import TYPE_CHECKING, Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import (
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from pywam.lib.const import Feature
from pywam.lib.playlist import (
    PLAYLIST_MIME_TYPES,
    parse_playlist,
)
from pywam.lib.url import (
    SUPPORTED_MIME_TYPES,
    UrlMediaItem,
)
from pywam.speaker import Speaker

from . import media_browser
from .const import LOGGER
from .wam_entity import WamEntity, async_check_connection

if TYPE_CHECKING:
    from . import WamConfigEntry
    from .wam_device import SamsungWamDevice


WAM_TO_REPEAT = {
    "off": RepeatMode.OFF,
    "all": RepeatMode.ALL,
    "one": RepeatMode.ONE,
}
REPEAT_TO_WAM = {ha: wam for wam, ha in WAM_TO_REPEAT.items()}
SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.GROUPING
)
FEATURES_MAPPING = {
    Feature.PLAY: MediaPlayerEntityFeature.PLAY,
    Feature.PAUSE: MediaPlayerEntityFeature.PAUSE,
    Feature.STOP: MediaPlayerEntityFeature.STOP,
    Feature.PREV: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    Feature.NEXT: MediaPlayerEntityFeature.NEXT_TRACK,
    Feature.SET_SHUFFLE: MediaPlayerEntityFeature.SHUFFLE_SET,
    Feature.SET_REPEAT: MediaPlayerEntityFeature.REPEAT_SET,
    Feature.PLAY_URL: MediaPlayerEntityFeature.PLAY_MEDIA,
    Feature.SELECT_SOURCE: MediaPlayerEntityFeature.SELECT_SOURCE,
}
# TODO: List all events to listen for
MONITORED_ATTRIBUTES: set[str] = set()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WAM media player from a config entry."""
    device = entry.runtime_data.device
    media_player = SamsungWamPlayer(device)

    async_add_entities([media_player])


class SamsungWamPlayer(WamEntity, MediaPlayerEntity):
    """Representation of a Samsung Wireless Audio media player."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(
        self,
        device: SamsungWamDevice,
    ) -> None:
        """Initialize the media player."""
        super().__init__(device)
        self._unjoining_group: bool = False

    @property
    def wam_monitored_attributes(self) -> set[str] | None:
        """Returns all attributes to monitor."""
        return MONITORED_ATTRIBUTES

    async def wam_async_added_to_hass_extra(self) -> None:
        """Run when entity about to be added to hass."""
        # We need to add the media player to the coordinator to be able
        # to handle grouping of speakers in a correct way.
        self.device.coordinator.add_media_player(self.entity_id, self)
        # We need to tell Home Assistant to update all media players after
        # we added a new one, otherwise initial grouping information will
        # not work since only loaded entities are returned.
        self.device.coordinator.update_hass_states()

    async def wam_async_will_remove_from_hass_extra(self) -> None:
        """Run when entity will be removed from hass."""
        self.device.coordinator.delete_media_player(self.entity_id)
        self.device.coordinator.update_hass_states()

    @property
    def name(self) -> str | None:
        """Speaker or group name."""
        if self.speaker.attribute.is_master:
            return f"(Master) {self.speaker.attribute.name}"
        if self.speaker.attribute.is_slave:
            return f"(Slave) {self.speaker.attribute.name}"

        return self.speaker.attribute.name

    @property
    def state(self):
        """Return the state of the device."""
        if self.speaker.attribute.state == "play":
            return MediaPlayerState.PLAYING
        if self.speaker.attribute.state == "pause":
            return MediaPlayerState.PAUSED

        return MediaPlayerState.IDLE  # "stop" is IDLE

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        supported_features = SUPPORTED_FEATURES
        for feature in self.speaker.supported_features:
            supported_features |= FEATURES_MAPPING.get(feature, 0)

        return supported_features

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._unique_id}-media_player"

    # ***************************************************************************
    # homeassistant.components.media_player.MediaPlayerEntity
    # ***************************************************************************

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self.speaker.attribute.volume:
            return self.speaker.attribute.volume / 100
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self.speaker.attribute.muted

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return None

    @property
    def media_content_type(self) -> str | None:
        """Content type of current playing media."""
        if self.source != "Wi-Fi":
            return None

        if self.app_name == "url":
            return MediaType.URL
        if self.app_name == "dlna":
            return MediaType.MUSIC
        if self.app_name == "TuneIn":
            return MediaType.CHANNEL

        return MediaType.APP

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.speaker.attribute.media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        # Not implemented
        return None

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        # Not implemented
        return None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.speaker.attribute.media_image_url

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        if self.app_name != "dlna":
            return True
        else:
            return False

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.speaker.attribute.media_title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.speaker.attribute.media_artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.speaker.attribute.media_album_name

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self.speaker.attribute.media_album_artist

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self.speaker.attribute.media_track

    @property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        if self.media_content_type == MediaType.CHANNEL:
            return self.media_title
        return None

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        # Not implemented
        return None

    @property
    def app_id(self) -> str | None:
        """ID of the current running app."""
        # Not implemented
        return None

    @property
    def app_name(self) -> str | None:
        """Name of the current running app."""
        return self.speaker.attribute.app_name

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self.speaker.attribute.source

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        return self.speaker.attribute.source_list

    @property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        return self.speaker.attribute.sound_mode

    @property
    def sound_mode_list(self) -> list[str] | None:
        """List of available sound modes."""
        return [mode.name for mode in self.speaker.attribute.sound_mode_list]

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        return self.speaker.attribute.shuffle_mode

    @property
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        return WAM_TO_REPEAT.get(self.speaker.attribute.repeat_mode)

    @property
    def group_members(self) -> list[str] | None:
        """List of members which are currently grouped together.

        A dynamic list of player entities which are currently grouped
        together for synchronous playback. If the platform has a concept
        of defining a group leader, the leader should be the first element
        in that list.
        """
        coordinator = self.device.coordinator

        if self.speaker.attribute.is_master:
            group_members = [self.entity_id]
            for entity_id, player in coordinator.get_all_available_media_players():
                if entity_id == self.entity_id:
                    continue
                if player.speaker.attribute.master_ip == self.speaker.ip:
                    group_members.append(entity_id)
            return group_members

        if self.speaker.attribute.is_slave:
            group_members = []
            for entity_id, player in coordinator.get_all_available_media_players():
                if player.speaker.ip == self.speaker.attribute.master_ip:
                    group_members.insert(0, entity_id)
                elif (
                    player.speaker.attribute.master_ip
                    == self.speaker.attribute.master_ip
                ):
                    group_members.append(entity_id)
            return group_members

        return None

    async def async_turn_on(self):
        """Turn the media player on."""
        raise NotImplementedError()

    async def async_turn_off(self):
        """Turn the media player off."""
        raise NotImplementedError()

    @async_check_connection(True)
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.speaker.set_mute(mute)

    @async_check_connection(True)
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.speaker.set_volume(int(volume * 100))

    @async_check_connection(False)
    async def async_media_play(self) -> None:
        """Send play command."""
        await self.speaker.cmd_play()

    @async_check_connection(False)
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.speaker.cmd_pause()

    @async_check_connection(False)
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.speaker.cmd_stop()

    @async_check_connection(False)
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.speaker.cmd_previous()

    @async_check_connection(False)
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.speaker.cmd_next()

    async def async_media_seek(self, position):
        """Send seek command."""
        raise NotImplementedError()

    async def _wam_async_get_playlist_first_item(
        self,
        url: str,
    ) -> UrlMediaItem | None:
        """Get the first item in a playlist."""
        LOGGER.debug("%s Downloading playlist from: %s", self.device.id, url)
        try:
            client = get_async_client(self.hass)
            # Safety net if one tries to send a large file as playlist.
            chunks = 0
            async with client.stream("GET", url) as response:
                async for data in response.aiter_text(chunk_size=4096):
                    if chunks > 1:
                        LOGGER.error("%s Playlist to large", self.device.id)
                        return
                    text = data
                    chunks += 1
        except Exception:
            LOGGER.warn("%s Could not get playlist from", self.device.id)
            return

        try:
            first_item = parse_playlist(text)[0]
            LOGGER.debug("%s Title from playlist: %s", self.device.id, first_item.title)
            LOGGER.debug(
                "%s Description from playlist: %s",
                self.device.id,
                first_item.description,
            )
            return first_item
        except IndexError:
            LOGGER.warn("%s Playlist did not contain any items", self.device.id)
            return
        except Exception as exc:
            LOGGER.warn("%s Error while parsing playlist: %s", self.device.id, exc)
            return

    async def _wam_async_get_headers(self, url: str) -> tuple[str, str, str, str]:
        """Check the http headers to determine how to handle the url."""
        # TODO: Do we need to mask the URL if it is an HA Core media source?
        # LOGGER.debug("%s Getting headers for: %s", self.device.id, url)
        try:
            client = get_async_client(self.hass)
            r = await client.head(url)
        except Exception:
            # TODO: Do we need to mask the URL if it is an HA Core media source?
            # LOGGER.error("%s Could not connect to: %s", self.device.id, url)
            return "", "", "", ""
        LOGGER.debug("%s Header: %s", self.device.id, r.headers)
        content_type = r.headers.get("content-type", "").split(";")[0]
        content_length = int(r.headers.get("content-length", 0))
        title = r.headers.get("icy-name", "")
        description = r.headers.get("icy-description", "")
        if description == "Unspecified description":
            description = ""
        LOGGER.debug("%s Content typ: %s", self.device.id, content_type)
        LOGGER.debug("%s Title from header: %s", self.device.id, title)
        LOGGER.debug("%s Description from header: %s", self.device.id, description)

        return content_type, content_length, title, description

    async def _wam_async_process_play_media_url(self, url: str) -> UrlMediaItem | None:
        """Get UrlMediaItem from a given URL to send to speaker."""
        # Get mime type from http header.
        c_type, c_length, title, description = await self._wam_async_get_headers(url)
        # TODO: Should we also try to get it from file suffix?
        # https://github.com/ctalkington/python-rokuecp/blob/main/src/rokuecp/helpers.py
        # https://docs.python.org/3/library/mimetypes.html

        # If it is a playable stream we send it to the speaker.
        if c_type in SUPPORTED_MIME_TYPES:
            return UrlMediaItem(url=url, title=title, description=description)

        # If it is a playlist we try to parse it.
        if c_type not in PLAYLIST_MIME_TYPES:
            return
        if c_length > 4096:
            LOGGER.warn(
                "%s Size of playlist is too large: %s", self.device.id, c_length
            )
            return
        if c_type == "text/html":
            LOGGER.warn(
                "%s Playlist format is unknown, but we will try to parse it",
                self.device.id,
            )
        item = await self._wam_async_get_playlist_first_item(url)
        if item is None:
            LOGGER.warn("%s Could not parser playlist", self.device.id)
            return

        c_type, c_length, title, description = await self._wam_async_get_headers(item)
        if c_type in SUPPORTED_MIME_TYPES:
            return UrlMediaItem(
                url=item.url,
                title=item.title or title,
                description=item.description or description,
                duration=item.duration,
            )

    @async_check_connection(False)
    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play a piece of media."""
        # TODO: Examine **kwargs, is it only extra for integration specific
        # implementations of service calls?
        # TODO: Examine media_type : media_type: MediaType | str
        # core/homeassistant/components/panasonic_viera/media_player.py
        # core/homeassistant/components/roku/media_player.py
        # TODO: Examine PlayMedia from async_process_play_media_url()
        # it has a .url and a .mime_type attribute.

        # Media Sources
        if media_source.is_media_source_id(media_id):
            media_type = MediaType.MUSIC
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            url = async_process_play_media_url(self.hass, play_item.url)
            media_item = await self._wam_async_process_play_media_url(url)
            # TODO: Do we need to mask the URL if it is an HA Core media source?
            # "%s Speaker doesn't support streaming of: %s", self.device.id, url
            if media_item is None:
                LOGGER.warn(
                    "%s Speaker doesn't support streaming of this media", self.device.id
                )
                return
            LOGGER.debug("%s Sending stream to speaker", self.device.id)
            await self.speaker.play_url(media_item)

        # TuneIn, Favorites
        elif media_browser.is_tunein_favorite_media_id(media_id):
            id = media_browser.resolve_media(media_id)
            for favorite in self.speaker.attribute.tunein_presets:
                if favorite.contentid == id:
                    await self.speaker.play_preset(favorite)
                    return
            LOGGER.error("%s TuneIn favorite not found on the speaker", self.device.id)

        # Error - media could not be played
        else:
            LOGGER.error(
                "%s Media (%s with type %s) is not supported",
                self.device.id,
                media_id,
                media_type,
            )

    @async_check_connection(True)
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.speaker.select_source(source)

    @async_check_connection(True)
    async def async_select_sound_mode(self, sound_mode) -> None:
        """Select sound mode."""
        for mode in self.speaker.attribute.sound_mode_list:
            if mode.name == sound_mode:
                await self.speaker.select_sound_mode(mode)

    async def async_clear_playlist(self):
        """Clear players playlist."""
        raise NotImplementedError()

    @async_check_connection(False)
    async def async_set_shuffle(self, shuffle) -> None:
        """Enable/disable shuffle mode."""
        await self.speaker.set_shuffle(shuffle)

    @async_check_connection(False)
    async def async_set_repeat(self, repeat) -> None:
        """Set repeat mode."""
        await self.speaker.set_repeat_mode(REPEAT_TO_WAM[repeat])

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_browser.async_browse_media(
            self.hass,
            self.speaker,
            media_content_id,
            media_content_type,
        )

    def _wam__get_speakers_to_group(self, entity_ids: list[str]) -> list[Speaker]:
        """Get the Speaker objects to group."""
        # Check that the media player is a SamsungWamPlayer and that
        # they are not already in another group.
        speakers: list[Speaker] = []
        for entity_id in entity_ids:
            if entity_id == self.entity_id:
                # This media player can be in list but should not be called
                continue
            try:
                player = self.device.coordinator.get_media_player(entity_id)
            except KeyError:
                LOGGER.error(
                    "%s %s is not a SamsungWam media player", self.device.id, entity_id
                )
                continue
            if not player.available:
                LOGGER.error(
                    "%s %s is not available (online) at the moment",
                    self.device.id,
                    entity_id,
                )
                continue
            if player.speaker.attribute.is_master:
                LOGGER.error(
                    "%s %s is already a master and can't be grouped",
                    self.device.id,
                    entity_id,
                )
                continue
            if player.speaker.attribute.is_slave:
                if player.speaker.attribute.master_ip != self.speaker.ip:
                    LOGGER.error(
                        "%s %s is slave in another group", self.device.id, entity_id
                    )
                    continue
            speakers.append(player.speaker)
        return speakers

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        # There should be no grouping operation in progress.
        if self.device.coordinator.grouping_in_progress:
            LOGGER.warn("%s Grouping operation is already in progress", self.device.id)
            return

        # A slave can't become a master.
        if self.speaker.attribute.is_slave:
            LOGGER.error("%s Speaker is already slave in a group", self.device.id)
            return

        # If this player is already a master we need to check that all
        # group members also are media players in HA to not break things.
        if self.speaker.attribute.is_master:
            if len(self.group_members) != self.speaker.attribute.number_of_speakers:
                LOGGER.error(
                    "%s All speakers in group is not available in Home Assistant",
                    self.device.id,
                )
                return

        # This can be called to add more speakers to the group. Then the
        # speakers list should be updated with the speakers already in
        # the group.
        if self.speaker.attribute.is_master:
            group_members.extend(self.group_members)

        speakers = self._wam__get_speakers_to_group(group_members)
        if len(speakers) == 0:
            LOGGER.error("%s No speakers to group", self.device.id)
            return

        self.device.coordinator.grouping_in_progress = True

        try:
            await self.speaker.create_group(speakers)
        except Exception as exc:
            LOGGER.error("%s Error while grouping speakers: %s", self.device.id, exc)
        finally:
            # We need to update all media players to get correct groups
            # but we have to wait because the slaves responds to the master.
            await asyncio.sleep(1)
            self.device.coordinator.update_hass_states()
            self.device.coordinator.grouping_in_progress = False

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        if not self.speaker.attribute.is_grouped:
            LOGGER.warn("%s Media player is not part of a group", self.device.id)
            return

        # There should be no grouping operation in progress.
        if self.device.coordinator.grouping_in_progress:
            LOGGER.warn("%s Grouping operation is already in progress", self.device.id)
            return

        # If speaker is master we delete the group
        if self.speaker.attribute.is_master:
            self._unjoining_group = True
            slaves = [
                self.device.coordinator.get_media_player(group_member).speaker
                for group_member in self.group_members[1:]
            ]
            if len(self.group_members) != self.speaker.attribute.number_of_speakers:
                LOGGER.error(
                    "%s All speakers in group is not available in Home Assistant",
                    self.device.id,
                )
                return
            try:
                await self.speaker.delete_group(slaves)
            except Exception as exc:
                LOGGER.error(
                    "%s Error while ungrouping speakers: %s", self.device.id, exc
                )
            finally:
                self._unjoining_group = False

        # If this player is slave, leave the group
        else:
            # Mini media player calls this for all speakers in the group, so
            # we have to check that the group isn't deleted by the master.
            await asyncio.sleep(2)
            if not self.speaker.attribute.is_grouped:
                return
            if self.device.coordinator.get_media_player(
                self.group_members[0]
            )._unjoining_group:
                return

            master = self.device.coordinator.get_media_player(
                self.group_members[0]
            ).speaker
            slaves = [
                self.device.coordinator.get_media_player(group_member).speaker
                for group_member in self.group_members[1:]
                if group_member != self.entity_id
            ]
            if len(self.group_members) != self.speaker.attribute.number_of_speakers:
                LOGGER.error(
                    "%s All speakers in group is not available in Home Assistant",
                    self.device.id,
                )
                return
            await self.speaker.leave_group(master, slaves)

        # We need to update all media players to get correct groups
        # but we have to wait because the slaves responds to the master.
        await asyncio.sleep(1)
        self.device.coordinator.update_hass_states()
