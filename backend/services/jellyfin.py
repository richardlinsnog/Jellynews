




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

    async def fetch_users(self) -> list[JellyfinUser]:
        """Return all users from the Jellyfin server."""
        resp = await self._get("/Users")
        return [JellyfinUser.model_validate(u) for u in resp.json()]

    # ------------------------------------------------------------------
    # Fetch items
    # ------------------------------------------------------------------

    async def get_latest_items(
        self,
        user_id: str | None = None,
        limit: int = 20,
        item_types: list[JellyfinItemType] | None = None,
        library_ids: list[str] | None = None,
    ) -> list[JellyfinItem]:
        """Return newest items visible to a user, optionally filtered by type and library."""
        if user_id is None:
            user_id = await self._resolve_user_id()

        if item_types is None:
            item_types = [
                JellyfinItemType.MOVIE,
                JellyfinItemType.SERIES,
                JellyfinItemType.AUDIO,
            ]

        include_item_types = ",".join(t.value for t in item_types)

        if library_ids:
            params = {
                "UserId": user_id,
                "Limit": limit,
                "IncludeItemTypes": include_item_types,
                "Recursive": "true",
                "SortBy": "DateCreated",
                "SortOrder": "Descending",
                "ParentIds": ",".join(library_ids),
                "Fields": "DateCreated,ProductionYear,Overview,ImageTags,Primary",
            }
            resp = await self._get(
                f"/Users/{user_id}/Items",
                params=params,
            )
        else:
            params = {
                "UserId": user_id,
                "Limit": limit,
                "IncludeItemTypes": include_item_types,
                "Recursive": "true",
                "SortBy": "DateCreated",
                "SortOrder": "Descending",
                "Fields": "DateCreated,ProductionYear,Overview,ImageTags,Primary",
            }
            resp = await self._get(
                f"/Users/{user_id}/Items/Latest",
                params=params,
            )
        items = JellyfinItemsResponse.from_api(resp.json()).items
        self._inject_image_urls(items)
        return items

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
            "Fields": "DateCreated,ProductionYear,Overview,ImageTags,Primary",
            "Limit": 200,
        }

        resp = await self._get(
            f"/Users/{user_id}/Items",
            params=params,
        )
        items = JellyfinItemsResponse.from_api(resp.json()).items
        self._inject_image_urls(items)
        return items

    def _inject_image_urls(self, items: list[JellyfinItem]) -> None:
        """Set image_url for each item from its ImageTags + base URL."""
        if not self._base_url:
            return
        for item in items:
            if item.image_tags and "Primary" in item.image_tags:
                tag = item.image_tags["Primary"]
                item.image_url = (
                    f"{self._base_url}/Items/{item.id}/Images/Primary"
                    f"?tag={tag}&quality=90"
                )

    async def fetch_branding_logo(self) -> tuple[bytes, str]:
        """Fetch the Jellyfin server's custom or default logo. Returns (content, content_type)."""
        if not self._base_url:
            raise JellyfinConnectionError("Jellyfin not configured")
        # Try the branding endpoint first, fall back to the default icon
        logo_paths = [
            "/Branding/Logo",
            "/web/img/banner-light.png",
            "/web/img/icon-transparent.png",
        ]
        for path in logo_paths:
            try:
                async with self._client() as client:
                    resp = await client.get(f"{self._base_url}{path}", timeout=10)
                    if resp.status_code == 200 and resp.content:
                        content_type = resp.headers.get("content-type", "image/png")
                        return resp.content, content_type
            except Exception:
                continue
        raise JellyfinConnectionError("Could not fetch server logo")

    async def fetch_image(self, item_id: str, tag: str = "") -> tuple[bytes, str]:
        """Fetch image bytes from Jellyfin. Returns (content, content_type)."""
        if not self._base_url:
            raise JellyfinConnectionError("Jellyfin not configured")
        url = f"{self._base_url}/Items/{item_id}/Images/Primary"
        params = {"maxWidth": 160, "maxHeight": 240, "quality": 60}
        if tag:
            params["tag"] = tag
        async with self._client() as client:
            resp = await client.get(url, params=params, timeout=15)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            return resp.content, content_type

    async def get_server_name(self) -> str | None:
        """Return the friendly server name, cached after first fetch."""
        try:
            info = await self.get_server_info()
            return info.name
        except Exception:
            return None

    async def fetch_library_names(self) -> list[str]:
        """Return the display names of all virtual folders (libraries)."""
        user_id = await self._resolve_user_id()
        resp = await self._get(f"/Users/{user_id}/Views")
        data = resp.json()
        return [item.get("Name", "") for item in data.get("Items", [])]

    async def get_libraries(self) -> list[dict]:
        """Return list of libraries with id, name and collection_type."""
        resp = await self._get("/Library/VirtualFolders")
        data = resp.json()
        return [
            {
                "id": item.get("ItemId", ""),
                "name": item.get("Name", ""),
                "collection_type": item.get("CollectionType") or "",
            }
            for item in data
        ]

    @staticmethod
    def library_types_to_item_types(libraries: list[dict], library_names: list[str]) -> list[JellyfinItemType]:
        """Convert selected library names to Jellyfin item types for filtering.
        'movies' → Movie, 'tvshows' → Series, no collection_type → all.
        """
        types: set[JellyfinItemType] = set()
        name_map = {lib["name"]: lib["collection_type"] for lib in libraries}
        for name in library_names:
            ct = name_map.get(name, "")
            if ct == "movies":
                types.add(JellyfinItemType.MOVIE)
            elif ct == "tvshows":
                types.add(JellyfinItemType.SERIES)
            elif ct == "music":
                types.add(JellyfinItemType.AUDIO)
            else:
                # Mixed library — include all
                types.update([JellyfinItemType.MOVIE, JellyfinItemType.SERIES, JellyfinItemType.AUDIO])
        return list(types) if types else [JellyfinItemType.MOVIE, JellyfinItemType.SERIES, JellyfinItemType.AUDIO]








