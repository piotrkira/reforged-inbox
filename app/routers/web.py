from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.config import AppConfig
from app.database import engine
from app.models import PatchRelay, PatchSeries
from app.utils import timesince

router = APIRouter()
templates = Jinja2Templates(directory="templates")

templates.env.filters["timesince"] = timesince


def get_session():
    with Session(engine) as session:
        yield session


@router.get("/")
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    relays = session.exec(select(PatchRelay)).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "relays": relays,
        },
    )


@router.get("/relay/{relay_name}")
def relay(request: Request, relay_name: str, session: Session = Depends(get_session)) -> HTMLResponse:
    relay = session.exec(select(PatchRelay).where(PatchRelay.name == relay_name)).one_or_none()

    if relay is None:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={},
        )

    return templates.TemplateResponse(
        request=request,
        name="relay.html",
        context={
            "relay": relay,
        },
    )


@router.get("/relay/{relay_name}/patch-series/{id}")
def patch_series(request: Request, relay_name: str, id: int, session: Session = Depends(get_session)) -> HTMLResponse:
    series = session.get(PatchSeries, id)
    relay = session.exec(select(PatchRelay).where(PatchRelay.name == relay_name)).one_or_none()

    if series is None:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={},
        )

    relay_config = AppConfig.relay[relay_name]
    mailing_list_url = f"{relay_config.public_inbox_url}/{relay_config.mailing_list}"

    return templates.TemplateResponse(
        request=request,
        name="patch_series.html",
        context={
            "series": series,
            "relay": relay,
            "mailing_list_url": mailing_list_url,
        },
    )
