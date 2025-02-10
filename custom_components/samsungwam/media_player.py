"""The Samsung Wireless Audio media player platform."""

from __future__ import annotations

import datetime as dt
import functools
import mimetypes
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import is_hass_url
from pywam.lib.const import Feature
from pywam.lib.playlist import PLAYLIST_MIME_TYPES
from pywam.lib.url import (
    SUPPORTED_MIME_TYPES,
    UrlMediaItem,
)

from . import media_browser
from .const import LOGGER
from .exceptions import WamGroupError
from .wam_entity import WamEntity, async_check_connection
from .wam_url import (
    async_get_http_headers,
    async_get_playlist_item,
)

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
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SELECT_SOURCE
)
# PLAY is always supported as a workaround for Mini Media Player
# who calls play_pause when pause is clicked, and not pause.
FEATURES_MAPPING = {
    # Feature.PLAY: MediaPlayerEntityFeature.PLAY,
    Feature.PAUSE: MediaPlayerEntityFeature.PAUSE,
    Feature.STOP: MediaPlayerEntityFeature.STOP,
    Feature.PREV: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    Feature.NEXT: MediaPlayerEntityFeature.NEXT_TRACK,
    Feature.SET_SHUFFLE: MediaPlayerEntityFeature.SHUFFLE_SET,
    Feature.SET_REPEAT: MediaPlayerEntityFeature.REPEAT_SET,
    Feature.PLAY_URL: MediaPlayerEntityFeature.PLAY_MEDIA,
}
MONITORED_ATTRIBUTES: set[str] = {
    "name",
    "volume",
    "muted",
    "state",
    "repeat_mode",
    "shuffle_mode",
    "source_list",
    "source",
    "app_name",
    "media_title",
    "media_artist",
    "media_album_name",
    "media_album_artist",
    "media_track",
    "media_image_url",
    "media_duration",
    "media_position",
    "sound_mode_list",
    "sound_mode",
}
MASTER_ATTRIBUTES: set[str] = {
    "state",
    "repeat_mode",
    "shuffle_mode",
    "app_name",
    "media_title",
    "media_artist",
    "media_album_name",
    "media_album_artist",
    "media_track",
    "media_image_url",
    "media_duration",
    "media_position",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WAM media player from a config entry."""
    device = entry.runtime_data.device
    media_player = SamsungWamPlayer(device)

    async_add_entities([media_player])


def master_property(func):
    """Return masters property if grouped."""

    @functools.wraps(func)
    def wrapper_master_property(self: SamsungWamPlayer, *args, **kwargs):
        if self.group_members and self.entity_id != self.group_members[0]:
            master = self.device.coordinator.get_media_player(self.group_members[0])
            return getattr(master, func.__name__, None)
        return func(self, *args, **kwargs)

    return wrapper_master_property


class SamsungWamPlayer(WamEntity, MediaPlayerEntity):
    """Representation of a Samsung Wireless Audio media player."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(
        self,
        device: SamsungWamDevice,
    ) -> None:
        """Initialize the media player."""
        super().__init__(device)

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

    @callback
    def wam_updates_from_device(
        self, attributes: dict[str, Any], force_update: bool = False
    ) -> None:
        """Receives state changes from SamsungWamDevice."""
        # Override WamEntity method so that we can write ha state on
        # slave media players when property should be same as master.
        if force_update:
            self.async_write_ha_state()
            return
        if self.wam_monitored_attributes.intersection(attributes.keys()):
            self.async_write_ha_state()
        if self.group_members and self.entity_id == self.group_members[0]:
            if MASTER_ATTRIBUTES.intersection(attributes.keys()):
                # Update state of all slave media players
                for player_id in self.group_members[1:]:
                    player = self.device.coordinator.get_media_player(player_id)
                    player.async_write_ha_state()

    @property
    def name(self) -> str | None:
        """Speaker or group name."""
        if self.speaker.attribute.is_master:
            return f"(Master) {self.speaker.attribute.name}"
        if self.speaker.attribute.is_slave:
            return f"(Slave) {self.speaker.attribute.name}"

        return self.speaker.attribute.name

    @property
    @master_property
    def state(self):
        """Return the state of the device."""
        if self.speaker.attribute.state == "play":
            return MediaPlayerState.PLAYING
        if self.speaker.attribute.state == "pause":
            return MediaPlayerState.PAUSED
        if self.speaker.attribute.state == "resume":
            return MediaPlayerState.PLAYING

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
    @master_property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return None

    @property
    @master_property
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
    @master_property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.speaker.attribute.media_duration

    @property
    @master_property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        # Not implemented
        return None

    @property
    @master_property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        # Not implemented
        return None

    @property
    @master_property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.speaker.attribute.media_image_url

    @property
    @master_property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        if self.app_name != "dlna":
            return True
        else:
            return False

    @property
    @master_property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.speaker.attribute.media_title

    @property
    @master_property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.speaker.attribute.media_artist

    @property
    @master_property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.speaker.attribute.media_album_name

    @property
    @master_property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self.speaker.attribute.media_album_artist

    @property
    @master_property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self.speaker.attribute.media_track

    @property
    @master_property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        if self.media_content_type == MediaType.CHANNEL:
            return self.media_title
        return None

    @property
    @master_property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        # Not implemented
        return None

    @property
    @master_property
    def app_id(self) -> str | None:
        """ID of the current running app."""
        # Not implemented
        return None

    @property
    @master_property
    def app_name(self) -> str | None:
        """Name of the current running app."""
        return self.speaker.attribute.app_name

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        # If speaker is slave we return the master as source
        if self.group_members and self.entity_id != self.group_members[0]:
            return self.device.coordinator.get_media_player(self.group_members[0]).name
        return self.speaker.attribute.source

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        # If media player is slave return name of master as only source
        if self.group_members and self.entity_id != self.group_members[0]:
            return [
                self.device.coordinator.get_media_player(self.group_members[0]).name
            ]
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
    @master_property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        return self.speaker.attribute.shuffle_mode

    @property
    @master_property
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

    @async_check_connection(False)
    async def async_play_media(  # noqa: C901
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play a piece of media.

        Arguments:
            media_type:
                A media type. Must be one of `music` or `playlist`.
                For `music` media_id should be a url pointing to a
                supported media format and codec.
                For `playlist` media_id should be a url pointing to
                supported playlist format.
                `channel` is for favorites, but not used yet.
            media_id:
                A media identifier.
            **kwargs:
                This integration doesn't support more arguments. To see
                what is available for the future, please visit:
                https://www.home-assistant.io/integrations/media_player/

        """
        # TODO: Implement extra arguments for title and thumb.
        LOGGER.debug(
            "%s media_type = %s, media_id = %s", self.device.id, media_type, media_id
        )

        # Media Sources
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            LOGGER.debug(
                "%s PlayMedia.mime_type: %s, PlayMedia.url: %s",
                self.device.id,
                play_item.mime_type,
                play_item.url,
            )
            url = async_process_play_media_url(self.hass, play_item.url)

            # If URL points to Home Assistant (local media and TTS) we
            # trust the PlayMedia mime type.
            if is_hass_url(self.hass, url):
                if play_item.mime_type in SUPPORTED_MIME_TYPES:
                    LOGGER.debug(
                        "%s Sending Home Assistant source stream to speaker",
                        self.device.id,
                    )
                    media_item = UrlMediaItem(url)
                    await self.speaker.play_url(media_item)
                elif play_item.mime_type in PLAYLIST_MIME_TYPES:
                    LOGGER.debug(
                        "%s media_id is a playlist - redirecting", self.device.id
                    )
                    await self.async_play_media(
                        media_type=MediaType.PLAYLIST, media_id=url
                    )
            # Otherwise we need to guess mime type or check http header.
            # Radio Stations Integration can return wrong mime type when
            # when it is a playlist.
            else:
                LOGGER.debug(
                    "%s media_id is not a local url - we need to check mime type",
                    self.device.id,
                )
                header = await async_get_http_headers(self, play_item.url)
                mime = mimetypes.guess_type(play_item.url)[0]
                if not mime:
                    mime = header.content_type
                if mime in SUPPORTED_MIME_TYPES:
                    await self.async_play_media(
                        media_type=MediaType.MUSIC, media_id=play_item.url
                    )
                elif mime in PLAYLIST_MIME_TYPES:
                    await self.async_play_media(
                        media_type=MediaType.PLAYLIST, media_id=play_item.url
                    )
            return

        # TuneIn, Favorites
        if media_browser.is_tunein_favorite_media_id(media_id):
            id = media_browser.resolve_media(media_id)
            for favorite in self.speaker.attribute.tunein_presets:
                if favorite.contentid == id:
                    await self.speaker.play_preset(favorite)
                    return
            raise TypeError(
                f"{self.device.id} TuneIn favorite not found on the speaker"
            )

        # URL (Music)
        if media_type == "music":
            LOGGER.debug("%s Will se if we can play: %s", self.device.id, media_id)
            header = await async_get_http_headers(self, media_id)
            mime = mimetypes.guess_type(media_id)[0]
            if not mime:
                mime = header.content_type
            LOGGER.debug("%s Mime type: %s", self.device.id, mime)
            if mime in SUPPORTED_MIME_TYPES:
                LOGGER.debug("%s Sending URL to speaker: %s", self.device.id, media_id)
                media_item = UrlMediaItem(media_id, header.title, header.description)
                await self.speaker.play_url(media_item)
                return
            else:
                raise TypeError(
                    f"{self.device.id} Given url is not a supported media type"
                )

        # Playlist
        if media_type == "playlist":
            LOGGER.debug(
                "%s Will se if we can parse playlist: %s", self.device.id, media_id
            )
            header = await async_get_http_headers(self, media_id)
            mime = mimetypes.guess_type(media_id)[0]
            if not mime:
                mime = header.content_type
            LOGGER.debug("%s Mime type: %s", self.device.id, mime)
            if mime in PLAYLIST_MIME_TYPES:
                # TODO: Make use of parsed media information from playlist.
                # To do this we need to implement the `extra` argument.
                media_item = await async_get_playlist_item(self, media_id, 1)
                await self.async_play_media(
                    media_type=MediaType.MUSIC, media_id=media_item.url
                )
                return
            else:
                raise TypeError(f"{self.device.id} Playlist format is not supported")

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

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        LOGGER.debug("%s Join players: %s", self.device.id, group_members)

        # Remove this media player from the group_members list
        if self.entity_id in group_members:
            group_members = [i for i in group_members if i != self.entity_id]

        # Call coordinator to perform the grouping operation
        try:
            self.device.coordinator.add_speakers_to_group(self.entity_id, group_members)
        except WamGroupError:
            raise ServiceValidationError("Error while grouping speakers") from None
        except Exception as exc:
            LOGGER.error("%s Error while grouping speakers", self.device.id)
            raise HomeAssistantError("Error while grouping speakers") from exc

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        LOGGER.debug("%s Unjoin player", self.device.id)

        # Ignore unjoin calls to masters to support mini media player
        if self.speaker.attribute.is_master:
            LOGGER.debug("%s Media player is master, ignoring unjoin", self.device.id)
            return

        # Call coordinator to perform the grouping operation
        try:
            self.device.coordinator.remove_speaker_from_group(
                self.group_members[0], self.entity_id
            )
        except WamGroupError:
            raise ServiceValidationError("Error while ungrouping speakers") from None
        except Exception as exc:
            LOGGER.error("%s Error while ungrouping speakers", self.device.id)
            raise HomeAssistantError("Error while ungrouping speakers") from exc
