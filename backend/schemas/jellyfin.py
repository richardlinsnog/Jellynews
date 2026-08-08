


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

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    has_password: bool = Field(default=False, alias="HasPassword")


class JellyfinItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    type: JellyfinItemType = Field(alias="Type")
    production_year: int | None = Field(default=None, alias="ProductionYear")
    date_created: datetime.datetime = Field(alias="DateCreated")
    library_name: str | None = Field(default=None, alias="LibraryName")


class JellyfinItemsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[JellyfinItem] = Field(default_factory=list, alias="Items")
    total_record_count: int = Field(default=0, alias="TotalRecordCount")


class JellyfinServerInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="Id")
    name: str = Field(alias="ServerName")
    version: str = Field(alias="Version")
