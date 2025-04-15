import datetime

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from .database import engine


class PatchSeries(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(unique=True)
    patch_relay_id: int | None = Field(default=None, foreign_key="patchrelay.id", nullable=False)
    patch_relay: "PatchRelay" = Relationship(back_populates="patch_series")
    patch_series_revisions: list["PatchSeriesRevision"] = Relationship(back_populates="patch_series")
    branch_name: str = Field(unique=True)
    author_email: EmailStr
    merge_request_url: str | None = Field(default=None, unique=True)


class PatchSeriesRevision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    patch_series_id: int | None = Field(default=None, foreign_key="patchseries.id")
    version: int
    msg_id: str
    patch_series: PatchSeries = Relationship(back_populates="patch_series_revisions")
    processed: datetime.datetime | None = Field(default=None)
    synced: bool = Field(default=False)
    error: str | None = Field(default=None)
    __table_args__ = (UniqueConstraint("patch_series_id", "version"),)


class PatchRelay(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    name: str = Field(unique=True)
    last_poll: datetime.datetime | None = Field(default=None)
    patch_series: list[PatchSeries] = Relationship(back_populates="patch_relay")


SQLModel.metadata.create_all(engine)
