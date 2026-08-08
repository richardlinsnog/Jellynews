


from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JellyfinItemType(str, Enum):
    MOVIE = "Movie"
    SERIES = "Series"
    SEASON = "Season"
    EPISODE = "Episode"
    AUDIO = "Audio"


class JellyfinUser(BaseModel):
    id: str
    name: str
    has_password: bool = Field(default=False, alias="HasPassword")

    model_config = {"populate_by_name": True}


class JellyfinItem(BaseModel):
    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    type: JellyfinItemType = Field(alias="Type")
    production_year: int | None = Field(default=None, alias="ProductionYear")
    date_created: datetime.datetime = Field(alias="DateCreated")
    library_name: str | None = Field(default=None)

    model_config = {"populate_by_name": True}


class JellyfinItemsResponse(BaseModel):
    items: list[JellyfinItem] = Field(default_factory=list, alias="Items")
    total_record_count: int = Field(default=0, alias="TotalRecordCount")

    model_config = {"populate_by_name": True}


class JellyfinServerInfo(BaseModel):
    id: str = Field(alias="Id")
    name: str = Field(alias="ServerName")
    version: str = Field(alias="Version")

    model_config = {"populate_by_name": True}
