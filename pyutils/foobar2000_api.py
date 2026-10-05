"""Small reusable client for the foobar2000 Web API used by NumHand.

This module contains transport concerns only. Decisions about file selection
and UI behavior belong to the caller.
"""
from __future__ import annotations

from typing import Any

import requests


class Foobar2000Api:
    def __init__(self, base_url: str = "http://localhost:8880", timeout: float = 1.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, **kwargs) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def player(self) -> dict[str, Any]:
        return self._get("/api/player")

    def playlist_items(
        self,
        playlist_id: int,
        start: int = 0,
        end: int = 20000,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._get(
            f"/api/playlists/{playlist_id}/items/{start}:{end}",
            params={"columns": columns or ["%path%"]},
        )
        playlist_items = payload.get("playlistItems", {})
        if isinstance(playlist_items, dict) and "items" in playlist_items:
            return playlist_items["items"]
        return payload.get("items", [])

    def current_path(self) -> str | None:
        player = self.player().get("player", {})
        item = player.get("activeItem")
        if not item:
            return None

        playlist_id = item.get("playlistId")
        index = item.get("index")
        if playlist_id is None or index is None:
            return None

        items = self.playlist_items(
            playlist_id,
            start=index,
            end=index + 1,
            columns=["%path%"],
        )
        if not items:
            return None

        columns = items[0].get("columns", [])
        return columns[0] if columns else None
