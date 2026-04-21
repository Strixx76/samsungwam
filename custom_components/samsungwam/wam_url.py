"""Helpers for handling URL playback and playlists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers.httpx_client import get_async_client
from pywam.lib.playlist import parse_playlist
from pywam.lib.url import UrlMediaItem

from .const import LOGGER

if TYPE_CHECKING:
    from .media_player import SamsungWamPlayer


@dataclass
class HttpHeaderInfo:
    """Container for http headers."""

    content_type: str
    content_length: int
    title: str
    description: str


async def async_check_redirect(player: SamsungWamPlayer, url: str) -> str:
    """Check if url is being redirected and return new url if needed."""

    LOGGER.debug("%s Checking for redirects: %s", player.device.id, url)

    try:
        client = get_async_client(player.hass)
        response = await client.head(url, follow_redirects=False)
    except Exception as exc:
        raise ConnectionError("Could not connect to server") from exc

    LOGGER.debug("%s Response code: %s", player.device.id, response.status_code)

    if response.status_code in (301, 302, 307, 308):
        new_url = response.headers.get("location", None)
        LOGGER.debug(
            "%s is being redirected to: %s", player.device.id, new_url
        )
        return new_url

    return url


async def async_get_http_headers(player: SamsungWamPlayer, url: str) -> HttpHeaderInfo:
    """Get information from http headers."""

    LOGGER.debug("%s Getting headers for: %s", player.device.id, url)

    try:
        client = get_async_client(player.hass)
        response = await client.head(url, follow_redirects=False)
    except Exception as exc:
        raise ConnectionError("Could not connect to server") from exc

    LOGGER.debug("%s Response code: %s", player.device.id, response.status_code)

    if response.status_code in (301, 302, 307, 308):
        raise ConnectionError("To many redirects.")

    if response.status_code != 200:
        raise ConnectionError(f"HTTP error: {response.status_code}")

    content_type = response.headers.get("content-type", "").split(";")[0]
    content_length = int(response.headers.get("content-length", 0))
    title = response.headers.get("icy-name", "")
    description = response.headers.get("icy-description", "")
    if description == "Unspecified description":
        description = ""

    return HttpHeaderInfo(content_type, content_length, title, description)


async def async_get_playlist_item(
    player: SamsungWamPlayer, url: str, idx: int
) -> UrlMediaItem:
    """Get an item in a playlist."""

    LOGGER.debug("%s Downloading playlist from: %s", player.device.id, url)
    header = await async_get_http_headers(player, url)
    if header.content_length > 4096:
        raise ValueError("Playlist too large")
    try:
        client = get_async_client(player.hass)
        playlist = ""
        # Safety net if one tries to send a large file as playlist.
        chunks = 0
        async with client.stream("GET", url, follow_redirects=True) as response:
            async for data in response.aiter_text(chunk_size=4096):
                if chunks > 0:
                    raise ValueError("This does not seem to be a playlist")
                playlist = data
                chunks += 1
    except Exception as exc:
        raise ConnectionError("Could not get playlist") from exc

    try:
        item = parse_playlist(playlist)[idx - 1]
        LOGGER.debug("%s Title: %s", player.device.id, item.title)
        LOGGER.debug(
            "%s Description: %s",
            player.device.id,
            item.description,
        )
        return item
    except IndexError as exc:
        raise IndexError("Playlist did not contain any items") from exc
    except Exception as exc:
        raise Exception("Error while parsing playlist") from exc
