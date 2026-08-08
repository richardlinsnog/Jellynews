
"""Unit tests for JellyfinService using mocked HTTP layer."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from schemas.jellyfin import JellyfinItemType
from services.jellyfin import (
    JellyfinAuthError,
    JellyfinConnectionError,
    JellyfinService,
)

FAKE_BASE = "http://jellyfin.local:8096"
FAKE_KEY = "fake-api-key-123"

USER_ADMIN = {"Id": "u-admin", "Name": "admin", "HasPassword": True}
USER_VIEWER = {"Id": "u-viewer", "Name": "viewer", "HasPassword": False}

ITEM_MOVIE = {
    "Id": "item-1",
    "Name": "Test Movie",
    "Type": "Movie",
    "ProductionYear": 2024,
    "DateCreated": "2024-01-15T10:30:00.0000000Z",
    "LibraryName": "Movies",
}

ITEM_SERIES = {
    "Id": "item-2",
    "Name": "Test Series",
    "Type": "Series",
    "ProductionYear": 2024,
    "DateCreated": "2024-02-15T10:30:00.0000000Z",
    "LibraryName": "TV Shows",
}

SERVER_INFO = {"Id": "srv-1", "ServerName": "MyJellyfin", "Version": "10.9.0"}


def _mock_resp(json_data: object) -> MagicMock:
    """Build a mock response with a working .json() method."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = 200
    return resp


# ---------------------------------------------------------------------------
# Init / configuration
# ---------------------------------------------------------------------------


class TestJellyfinServiceInit:
    def test_is_configured_true(self) -> None:
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        assert svc.is_configured is True

    def test_is_configured_false_no_url(self) -> None:
        svc = JellyfinService(base_url=None, api_key=FAKE_KEY)
        assert svc.is_configured is False

    def test_is_configured_false_no_key(self) -> None:
        svc = JellyfinService(base_url=FAKE_BASE, api_key=None)
        assert svc.is_configured is False

    def test_strips_trailing_slash(self) -> None:
        svc = JellyfinService(base_url=FAKE_BASE + "/", api_key=FAKE_KEY)
        assert svc._base_url == FAKE_BASE


class TestJellyfinAuthHeaders:
    def test_auth_headers_contain_token_and_api_key(self) -> None:
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        headers = svc._auth_headers()
        assert "X-Emby-Authorization" in headers
        assert "MediaBrowser" in headers["X-Emby-Authorization"]
        assert headers["X-MediaBrowser-Token"] == FAKE_KEY

    def test_auth_headers_work_without_api_key(self) -> None:
        svc = JellyfinService(base_url=FAKE_BASE, api_key=None)
        headers = svc._auth_headers()
        assert "X-Emby-Authorization" in headers
        assert "X-MediaBrowser-Token" not in headers


class TestClientMethod:
    def test_client_raises_when_base_url_is_none(self) -> None:
        svc = JellyfinService(base_url=None, api_key=FAKE_KEY)
        with pytest.raises(
            JellyfinConnectionError,
            match="Jellyfin base URL is not configured",
        ):
            svc._client()


# ---------------------------------------------------------------------------
# _resolve_user_id
# ---------------------------------------------------------------------------


class TestResolveUserId:
    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_resolve_admin_user(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp([USER_ADMIN])
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        uid = await svc._resolve_user_id()
        assert uid == "u-admin"

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_resolve_fallback_first_user(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp([USER_VIEWER])
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        uid = await svc._resolve_user_id()
        assert uid == "u-viewer"

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_no_users_raises_connection_error(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp([])
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        with pytest.raises(JellyfinConnectionError, match="No users found"):
            await svc._resolve_user_id()

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_cached_user_id_no_second_request(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp([USER_ADMIN])
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        uid1 = await svc._resolve_user_id()
        uid2 = await svc._resolve_user_id()
        assert uid1 == uid2 == "u-admin"
        assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Server info / ping
# ---------------------------------------------------------------------------


class TestServerInfo:
    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_get_server_info(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp(SERVER_INFO)
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        info = await svc.get_server_info()
        assert info.name == "MyJellyfin"
        assert info.version == "10.9.0"
        assert info.id == "srv-1"

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_ping_success(self, mock_get: AsyncMock) -> None:
        resp = _mock_resp(None)
        resp.status_code = 200
        mock_get.return_value = resp
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        assert await svc.ping() is True

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_ping_failure(self, mock_get: AsyncMock) -> None:
        resp = _mock_resp(None)
        resp.status_code = 500
        mock_get.return_value = resp
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        assert await svc.ping() is False


# ---------------------------------------------------------------------------
# Auth error handling — side_effect raises to bypass _get internals
# ---------------------------------------------------------------------------


class TestAuthErrors:
    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_401_raises_auth_error(self, mock_get: AsyncMock) -> None:
        mock_get.side_effect = JellyfinAuthError("Jellyfin API key is invalid")
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        with pytest.raises(JellyfinAuthError):
            await svc._resolve_user_id()

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_500_raises_connection_error(self, mock_get: AsyncMock) -> None:
        mock_get.side_effect = JellyfinConnectionError("Jellyfin server error: 500")
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        with pytest.raises(JellyfinConnectionError):
            await svc._resolve_user_id()


# ---------------------------------------------------------------------------
# get_latest_items
# ---------------------------------------------------------------------------


class TestGetLatestItems:
    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_returns_items_with_library_names(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp(
            {"Items": [ITEM_MOVIE, ITEM_SERIES], "TotalRecordCount": 2},
        )
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        svc._user_id = "u1"
        items = await svc.get_latest_items()
        assert len(items) == 2
        assert items[0].name == "Test Movie"
        assert items[0].library_name == "Movies"
        assert items[1].name == "Test Series"
        assert items[1].library_name == "TV Shows"

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_accepted_direct_user_id(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp(
            {"Items": [], "TotalRecordCount": 0},
        )
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        items = await svc.get_latest_items(user_id="direct-user")
        assert items == []

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_respects_limit_and_item_types_in_params(
        self,
        mock_get: AsyncMock,
    ) -> None:
        mock_get.return_value = _mock_resp(
            {"Items": [], "TotalRecordCount": 0},
        )
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        svc._user_id = "u1"
        await svc.get_latest_items(
            limit=5,
            item_types=[JellyfinItemType.AUDIO],
        )
        params = mock_get.call_args.kwargs["params"]
        assert params["Limit"] == 5
        assert params["IncludeItemTypes"] == "Audio"

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_default_item_types(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp(
            {"Items": [], "TotalRecordCount": 0},
        )
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        svc._user_id = "u1"
        await svc.get_latest_items()
        types = mock_get.call_args.kwargs["params"]["IncludeItemTypes"]
        assert "Movie" in types
        assert "Series" in types
        assert "Audio" in types


# ---------------------------------------------------------------------------
# get_items_since
# ---------------------------------------------------------------------------


class TestGetItemsSince:
    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_includes_min_date(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp(
            {"Items": [], "TotalRecordCount": 0},
        )
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        svc._user_id = "u1"
        since = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
        await svc.get_items_since(since=since)
        assert "MinDate" in mock_get.call_args.kwargs["params"]


# ---------------------------------------------------------------------------
# fetch_library_names
# ---------------------------------------------------------------------------


class TestFetchLibraryNames:
    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_returns_library_names(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp(
            {"Items": [{"Name": "Movies"}, {"Name": "TV Shows"}]},
        )
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        svc._user_id = "u1"
        names = await svc.fetch_library_names()
        assert names == ["Movies", "TV Shows"]

    @pytest.mark.asyncio
    @patch.object(JellyfinService, "_get", new_callable=AsyncMock)
    async def test_empty_libraries(self, mock_get: AsyncMock) -> None:
        mock_get.return_value = _mock_resp({"Items": []})
        svc = JellyfinService(base_url=FAKE_BASE, api_key=FAKE_KEY)
        svc._user_id = "u1"
        names = await svc.fetch_library_names()
        assert names == []
