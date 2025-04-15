from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.database import engine
from app.models import PatchSeries, PatchSeriesRevision

router = APIRouter(prefix="/api")


@router.get("/ping")
def ping():
    return "pong"


class PatchSeriesResponse(BaseModel):
    title: str
    author_email: str
    merge_request_url: str | None
    last_revision: int
    last_revision_msg_id: str


@router.get("/patch-series")
def get_patch_series(
    merge_request_url: str | None = None,
) -> list[PatchSeriesResponse]:
    response: list[PatchSeriesResponse] = []
    with Session(engine) as session:
        query = select(PatchSeries)
        if merge_request_url:
            query = query.where(PatchSeries.merge_request_url == merge_request_url)
        series = list(session.exec(query).all())
        for patch_series in series:
            revision_stmt = (
                select(PatchSeriesRevision)
                .where(
                    PatchSeriesRevision.patch_series_id == patch_series.id,
                    PatchSeriesRevision.synced == True,
                )
                .order_by(col(PatchSeriesRevision.version).desc())
            )
            last_revision = session.exec(revision_stmt).all()[0]
            response.append(
                PatchSeriesResponse(
                    title=patch_series.title,
                    author_email=patch_series.author_email,
                    merge_request_url=patch_series.merge_request_url,
                    last_revision=last_revision.version,
                    last_revision_msg_id=last_revision.msg_id,
                )
            )
    return response
