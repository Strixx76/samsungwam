"""The Samsung Wireless Audio browse media functions."""

from __future__ import annotations

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from pywam.speaker import Speaker

WAM_TUNEIN_FAV_URI_SCHEME = "wam_tunein_fav://"
WAM_TUNEIN_APP_URI_SCHEME = "wam_tunein_app://"


def is_tunein_favorite_media_id(media_id: str) -> bool:
    """Return True if media id is a TuneIn favorite."""
    if media_id.split("://")[0] + "://" == WAM_TUNEIN_FAV_URI_SCHEME:
        return True
    else:
        return False


def is_tunein_app_media_id(media_id: str) -> bool:
    """Return True if media id is from TuneIn app."""
    if media_id.split("://")[0] + "://" == WAM_TUNEIN_APP_URI_SCHEME:
        return True
    else:
        return False


def resolve_media(media_id: str) -> str:
    """Return media id without the scheme part."""
    return media_id.split("://", 1)[1]


def media_source_filter(item: BrowseMedia) -> bool:
    """Filter media from media source integration."""
    return item.media_content_type.startswith("audio/")


async def async_browse_root(hass, speaker: Speaker) -> BrowseMedia:
    """Return the root items for Samsung WAM speaker."""
    children = []

    # Favorites (TuneIn presets on speaker)
    if speaker.attribute.tunein_presets:
        children.append(
            BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id=WAM_TUNEIN_FAV_URI_SCHEME,
                media_content_type=MediaType.CHANNELS,
                title="TuneIn Favorites",
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.CHANNEL,
            )
        )

    # TuneIn App on speaker
    # TODO: To be implemented
    # children.append(
    # BrowseMedia(
    # media_class=MEDIA_CLASS_APP,
    # media_content_id=WAM_TUNEIN_APP_URI_SCHEME,
    # media_content_type=MEDIA_TYPE_APP,
    # title="TuneIn App",
    # can_play=False,
    # can_expand=False,
    # children_media_class=MEDIA_CLASS_DIRECTORY,
    # )
    # )

    # DLNA on speaker
    # TODO: To be implemented

    # Media Sources
    try:
        item = await media_source.async_browse_media(
            hass, None, content_filter=media_source_filter
        )
        # If domain is None, it's overview of available sources
        if item.domain is None:
            children.extend(item.children)  # type: ignore
        else:
            children.append(item)
    except BrowseError:
        pass

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="",
        title="Samsung WAM",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def async_browse_tunein_favorites(speaker: Speaker) -> BrowseMedia:
    """List TuneIn favorites."""

    favorites: list[BrowseMedia] = []

    for favorite in speaker.attribute.tunein_presets:
        favorites.append(
            BrowseMedia(
                media_class=MediaClass.CHANNEL,
                media_content_id=f"{WAM_TUNEIN_FAV_URI_SCHEME}{favorite.contentid}",
                media_content_type=MediaType.CHANNEL,
                title=favorite.title,
                can_play=True,
                can_expand=False,
                thumbnail=favorite.thumbnail,
            )
        )

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=WAM_TUNEIN_FAV_URI_SCHEME,
        media_content_type=MediaType.CHANNEL,
        title="TuneIn favorites",
        can_play=False,
        can_expand=True,
        children=favorites,
        children_media_class=MediaClass.CHANNEL,
    )


# TODO: Implement TuneIn browsing in pywam library
# async def async_browse_tunein_app(
#     speaker: Speaker, media_content_id: int
# ) -> list[BrowseMedia]:
#     """List folders or channels in TuneIn app."""


async def async_browse_media(
    hass,
    speaker: Speaker,
    media_content_id: str | None,
    media_content_type: MediaType | str | None = None,
) -> BrowseMedia:
    """Browse media."""

    if media_content_id is not None:
        # Browse media items from media source integration
        if media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                hass, media_content_id, content_filter=media_source_filter
            )

        # TuneIn, Favorites
        if is_tunein_favorite_media_id(media_content_id):
            return await async_browse_tunein_favorites(speaker)

    # TuneIn, App
    # TODO: To be implemented
    # if is_tunein_app_media_id(media_content_id):
    # return await async_browse_tunein_app(speaker, media_content_id)

    # DLNA on speaker
    # TODO: To be implemented

    # Root level for Samsung WAM
    return await async_browse_root(hass, speaker)
