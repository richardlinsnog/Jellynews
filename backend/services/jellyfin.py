




from __future__ import annotations

import datetime

import httpx
from core.config import settings
from core.logging import get_logger
from schemas.jellyfin import (
    JellyfinItem,
    JellyfinItemsResponse,
    JellyfinItemType,
    JellyfinServerInfo,
    JellyfinUser,
)

logger = get_logger(__name__)


class JellyfinConnectionError(Exception):
    """Raised when Jellyfin server is unreachable."""


class JellyfinAuthError(Exception):
    """Raised when Jellyfin API key is invalid."""


class JellyfinService:
    """Async client for the Jellyfin REST API.

    Resolves UserId automatically, fetches latest items by type,
    and tolerates multiple libraries.

    Credentials are injected — the caller is responsible for loading
    them from the database via SecretsVaultService.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._api_key = api_key
        self._user_id: str | None = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._api_key)

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        if not self._base_url:
            raise JellyfinConnectionError("Jellyfin base URL is not configured")
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._auth_headers(),
            timeout=httpx.Timeout(15.0),
        )

    def _auth_headers(self) -> dict[str, str]:
        token_parts = [
            'MediaBrowser Client="JellyNews"',
            f'Device="{settings.APP_ENV}"',
            f'DeviceId="jellynews-{settings.APP_ENV}"',
            'Version="0.1.0"',
        ]
        token = ", ".join(token_parts)
        headers: dict[str, str] = {
            "X-Emby-Authorization": token,
        }
        if self._api_key:
            headers["X-MediaBrowser-Token"] = self._api_key
        return headers

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with self._client() as client:
            resp = await client.get(path, params=params)
            self._raise_for_jellyfin_error(resp)
            return resp

    @staticmethod
    def _raise_for_jellyfin_error(resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise JellyfinAuthError("Jellyfin API key is invalid")
        if resp.status_code >= 500:
            raise JellyfinConnectionError(
                f"Jellyfin server error: {resp.status_code}",
            )

    # ------------------------------------------------------------------
    # Server info & health
    # ------------------------------------------------------------------

    async def get_server_info(self) -> JellyfinServerInfo:
        resp = await self._get("/System/Info")
        return JellyfinServerInfo.model_validate(resp.json())

    async def ping(self) -> bool:
        try:
            resp = await self._get("/System/Ping")
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # User resolution
    # ------------------------------------------------------------------

    async def _resolve_user_id(self) -> str:
        """Find an admin user or the first valid user in the Jellyfin server."""
        if self._user_id:
            return self._user_id

        resp = await self._get("/Users")
        users = [JellyfinUser.model_validate(u) for u in resp.json()]

        # Prefer an admin user
        admin = next((u for u in users if "admin" in u.name.lower()), None)
        user_id: str
        if admin:
            user_id = admin.id
        elif users:
            user_id = users[0].id
        else:
            raise JellyfinConnectionError("No users found in Jellyfin server")

        self._user_id = user_id
        logger.info("jellyfin_user_resolved", user_id=self._user_id)
        return user_id

    # ------------------------------------------------------------------
    # Fetch items
    # ------------------------------------------------------------------

    async def get_latest_items(
        self,
        user_id: str | None = None,
        limit: int = 20,
        item_types: list[JellyfinItemType] | None = None,
    ) -> list[JellyfinItem]:
        """Return newest items visible to a user, optionally filtered by type."""
        if user_id is None:
            user_id = await self._resolve_user_id()

        if item_types is None:
            item_types = [
                JellyfinItemType.MOVIE,
                JellyfinItemType.SERIES,
                JellyfinItemType.AUDIO,
            ]

        include_item_types = ",".join(t.value for t in item_types)
        params = {
            "UserId": user_id,
            "Limit": limit,
            "IncludeItemTypes": include_item_types,
            "Recursive": "true",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Fields": "ProductionYear",
        }

        resp = await self._get(
            f"/Users/{user_id}/Items/Latest",
            params=params,
        )
        data = JellyfinItemsResponse.model_validate(resp.json())
        return data.items

    async def get_items_since(
        self,
        since: datetime.datetime,
        user_id: str | None = None,
        item_types: list[JellyfinItemType] | None = None,
    ) -> list[JellyfinItem]:
        """Return items created after *since* (idempotency boundary)."""
        if user_id is None:
            user_id = await self._resolve_user_id()

        if item_types is None:
            item_types = [
                JellyfinItemType.MOVIE,
                JellyfinItemType.SERIES,
                JellyfinItemType.AUDIO,
            ]

        include_item_types = ",".join(t.value for t in item_types)
        params = {
            "UserId": user_id,
            "IncludeItemTypes": include_item_types,
            "Recursive": "true",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "MinDate": since.isoformat(),
            "Fields": "ProductionYear",
            "Limit": 200,
        }

        resp = await self._get(
            f"/Users/{user_id}/Items",
            params=params,
        )
        data = JellyfinItemsResponse.model_validate(resp.json())
        return data.items

    async def fetch_library_names(self) -> list[str]:
        """Return the display names of all virtual folders (libraries)."""
        user_id = await self._resolve_user_id()
        resp = await self._get(f"/Users/{user_id}/Views")
        data = resp.json()
        return [item.get("Name", "") for item in data.get("Items", [])]








