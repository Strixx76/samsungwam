"""The Samsung Wireless Audio media player platform."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pywam.lib.const import Feature

from homeassistant.const import STATE_IDLE, STATE_PLAYING, STATE_PAUSED
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    # MediaPlayerEnqueue,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import (
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import media_browser
from .const import (
    DOMAIN,
    ID_MAPPINGS,
    LOGGER,
    COORDINATOR,
)
from .coordinator import (
    async_check_response,
    SamsungWamCoordinator,
)


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
        # If the speaker is master in a group return the group name
        if self.speaker.attribute.is_master:
            return self.speaker.attribute.group_name

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

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.
        To be extended by integrations.

        Called when an entity has their entity_id and hass object
        assigned, before it is written to the state machine for the
        first time. Example uses: restore the state, subscribe to
        updates or set callback/dispatch function/listener.
        """
        self.speaker.events.register_subscriber(self._state_receiver)
        self.hass.data[DOMAIN][ID_MAPPINGS][self.entity_id] = self.speaker

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.
        To be extended by integrations.

        Called when an entity is about to be removed from Home Assistant.
        Example use: disconnect from the server or unsubscribe from
        updates.
        """
        self.speaker.events.unregister_subscriber(self._state_receiver)
        self.hass.data[DOMAIN][ID_MAPPINGS].pop(self.entity_id, None)

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated.
        To be extended by integrations.
        """

    async def async_removed_from_registry(self) -> None:
        """Run when entity has been removed from entity registry.
        To be extended by integrations.
        """

    # ***************************************************************************
    # homeassistant.components.media_player.MediaPlayerEntity
    # ***************************************************************************

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self.speaker.attribute.volume:
            return self.speaker.attribute.volume / 100

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
        if not self.app_name == "dlna":
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
        """A dynamic list of player entities which are currently grouped
        together for synchronous playback. If the platform has a concept
        of defining a group leader, the leader should be the first element
        in that list."""
        if self.speaker.attribute.is_master:
            group_members = [self.entity_id]
            for entity_id in self.hass.data[DOMAIN][ID_MAPPINGS]:
                speaker = self.hass.data[DOMAIN][ID_MAPPINGS][entity_id]
                if entity_id == self.entity_id:
                    continue
                if speaker.attribute.master_ip == self.speaker.ip:
                    group_members.append(entity_id)
            return group_members

        if self.speaker.attribute.is_slave:
            group_members = []
            for entity_id in self.hass.data[DOMAIN][ID_MAPPINGS]:
                speaker = self.hass.data[DOMAIN][ID_MAPPINGS][entity_id]
                if speaker.ip == self.speaker.attribute.master_ip:
                    group_members.insert(0, entity_id)
                if speaker.attribute.master_ip == self.speaker.attribute.master_ip:
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
        vol = int(volume * 100)
        await self.speaker.set_volume(vol)

    @async_check_connection
    async def async_media_play(self) -> None:
        """Send play command."""
        await self.speaker.cmd_play()

    @async_check_connection
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.speaker.cmd_pause()

    @async_check_connection
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.speaker.cmd_stop()

    @async_check_connection
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.speaker.cmd_previous()

    @async_check_connection
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.speaker.cmd_next()

    async def async_media_seek(self, position):
        """Send seek command."""
        raise NotImplementedError()

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        # enqueue: MediaPlayerEnqueue | None = None,
        # announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play a piece of media."""
        # Media Sources
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(self.hass, media_id)
            url = async_process_play_media_url(self.hass, play_item.url)
            LOGGER.debug("Sending url: %s", url)
            LOGGER.debug("With media type: %s", media_type)
            # Examples of url sent from Media Source:
            # http://webradio.dbmedia.se/streams/crr96.pls
            # http://fm02-ice.stream.khz.se/fm02_mp3
            # http://172.17.0.2:8123/api/tts_proxy/4f662742580deb5f5d4267d399fb5b5eddd3a1ed_en_-_google_translate.mp3?authSig=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJkOGRmYTE0ZTFkZWQ0MWQ1OTMyZjU2ZDQ1MmNlNjMwZSIsInBhdGgiOiIvYXBpL3R0c19wcm94eS80ZjY2Mjc0MjU4MGRlYjVmNWQ0MjY3ZDM5OWZiNWI1ZWRkZDNhMWVkX2VuXy1fZ29vZ2xlX3RyYW5zbGF0ZS5tcDMiLCJpYXQiOjE2NTUzNjE3NDAsImV4cCI6MTY1NTQ0ODE0MH0.mMmODussimHD0bxbrYhPWC5GOKzxxI-i6-JawXv1scg
            # await self.speaker.play_url(url)

        # TuneIn, Favorites
        elif media_browser.is_tunein_favorite_media_id(media_id):
            play_item = media_browser.resolve_media(media_id)
            for favorite in self.speaker.attribute.tunein_presets:
                if favorite.contentid == play_item:
                    await self.speaker.play_preset(favorite)
                    return
            LOGGER.error(
                "%s TuneIn favorite not found on the speaker", self.coordinator.id
            )

        # Error - media could not be played
        else:
            LOGGER.error(
                "%s Media (%s with type %s) is not supported",
                self.coordinator.id,
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

    @async_check_connection
    async def async_set_shuffle(self, shuffle) -> None:
        """Enable/disable shuffle mode."""
        await self.speaker.set_shuffle(shuffle)

    @async_check_connection
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
