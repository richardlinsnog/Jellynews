


from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class JellyfinItemType(str, Enum):
    MOVIE = "Movie"
    SERIES = "Series"
    SEASON = "Season"
    EPISODE = "Episode"
    AUDIO = "Audio"


class JellyfinUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="Id")
    name: str = Field(validation_alias="Name")
    has_password: bool = Field(default=False, validation_alias="HasPassword")


class JellyfinItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="Id")
    name: str = Field(validation_alias="Name")
    type: JellyfinItemType = Field(validation_alias="Type")
    production_year: int | None = Field(default=None, validation_alias="ProductionYear")
    date_created: datetime.datetime | None = Field(default=None, validation_alias="DateCreated")
    premiere_date: datetime.datetime | None = Field(default=None, validation_alias="PremiereDate")
    library_name: str | None = Field(default=None, validation_alias="LibraryName")
    overview: str | None = Field(default=None, validation_alias="Overview")
    image_url: str | None = Field(default=None)
    image_tags: dict | None = Field(default=None, validation_alias="ImageTags")

    @property
    def effective_date(self) -> datetime.datetime | None:
        return self.date_created or self.premiere_date


class JellyfinItemsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[JellyfinItem] = Field(default_factory=list, validation_alias="Items")
    total_record_count: int = Field(default=0, validation_alias="TotalRecordCount")

    @staticmethod
    def from_api(data: list | dict) -> "JellyfinItemsResponse":
        """Accept a plain list (GET /Items/Latest) or {Items: [...], TotalRecordCount: ...}."""
        if isinstance(data, list):
            return JellyfinItemsResponse.model_validate(
                {"Items": data, "TotalRecordCount": len(data)}
            )
        return JellyfinItemsResponse.model_validate(data)


class JellyfinServerInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="Id")
    name: str = Field(validation_alias="ServerName")
    version: str = Field(validation_alias="Version")
