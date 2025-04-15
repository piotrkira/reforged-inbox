import logging
import random
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import dramatiq
import redis.lock
from dramatiq.brokers.redis import RedisBroker
from redmail.email.sender import EmailSender
from sqlmodel import Session, func, select

from app.config import AppConfig, EmailConfig
from app.database import engine, redis_pool
from app.forge import PatchSeriesData, forge_registry
from app.git import GitPatchDoesNotApplyError, GitRepo, GitRepoManager
from app.inbox import PatchData, PublicInbox
from app.models import PatchRelay, PatchSeries, PatchSeriesRevision
from app.utils import parse_description_cover, parse_description_mbx

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


broker = RedisBroker(
    host=AppConfig.redis.host, password=AppConfig.redis.password, port=AppConfig.redis.port, db=AppConfig.redis.db
)
dramatiq.set_broker(broker)


class Email:
    def __init__(self, config: EmailConfig):
        self.email = EmailSender(
            config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            use_starttls=config.starttls,
        )
        self.sender = f"{config.name} <{config.email}>" if config.name else config.email

    def send(self, subject: str, receivers: list[str], text: str, reply_to: str | None = None):
        headers = {}
        if reply_to:
            headers["In-Reply-To"] = reply_to
            headers["References"] = reply_to
            self.email.send(
                headers=headers,
                subject=subject,
                sender=self.sender,
                # FIXME: remove
                # receivers=receivers,
                receivers=["piotr.kira@intel.com"],
                text=text,
            )
        pass


def get_database_time_now() -> datetime:
    with Session(engine) as session:
        res = session.exec(select(func.now()))
        date = res.one()
        return date


def get_or_create_patch_series(title: str, relay: PatchRelay, author_email: str) -> tuple[PatchSeries, bool]:
    with Session(engine) as session:
        patch_series = session.exec(select(PatchSeries).where(PatchSeries.title == title)).one_or_none()
        if patch_series:
            return patch_series, False

        branch_name = f"reforged-{random.randbytes(8).hex()}"
        patch_series = PatchSeries(
            title=title,
            patch_relay=relay,
            branch_name=branch_name,
            author_email=author_email,
        )
        session.add(patch_series)
        session.commit()
        session.refresh(patch_series)
        return patch_series, True


def get_or_create_patch_series_revision(
    patch_series: PatchSeries, patch_data: PatchData
) -> tuple[PatchSeriesRevision, bool]:
    with Session(engine) as session:
        patch_series_revision = session.exec(
            select(PatchSeriesRevision).where(
                PatchSeriesRevision.patch_series_id == patch_series.id,
                PatchSeriesRevision.version == patch_data.revision,
            )
        ).one_or_none()
        if patch_series_revision:
            return patch_series_revision, False
        patch_series_revision = PatchSeriesRevision(
            version=patch_data.revision,
            msg_id=patch_data.msg_id,
        )
        patch_series_revision.patch_series = patch_series
        session.add(patch_series_revision)
        session.commit()
        session.refresh(patch_series_revision)
        session.refresh(patch_series)
        return patch_series_revision, True


def save_patch_series_revision_to_db(
    patch_data: PatchData, patch_relay: PatchRelay
) -> tuple[PatchSeriesRevision, bool]:
    patch_series, created = get_or_create_patch_series(patch_data.title, patch_relay, patch_data.author_email)
    if created:
        logger.info(f"Created patch series ({patch_series.id}): {patch_series.title}")
    revision, created = get_or_create_patch_series_revision(patch_series, patch_data)
    if created:
        logger.info(f"Created patch series revision ({revision.id}): {revision.version} for {patch_series.title}")
    return revision, created


@dramatiq.actor(time_limit=60 * 1000)
def pull_patches(relay_name: str):
    logger.info(f"Pulling patches for {relay_name}")
    relay_config = AppConfig.relay[relay_name]

    time_now = get_database_time_now()
    inbox = PublicInbox(relay_config.public_inbox_url, relay_config.mailing_list)

    with Session(engine) as session:
        relay = session.exec(select(PatchRelay).where(PatchRelay.name == relay_name)).one()
    poll_date = (relay.last_poll if relay.last_poll else time_now) - timedelta(days=1)
    patches = inbox.get_patches(poll_date)
    new_patches = 0
    for patch in patches:
        patch_series, _ = get_or_create_patch_series(patch.title, relay, patch.author_email)
        patch_series_revision, created = get_or_create_patch_series_revision(patch_series, patch)
        if created:
            new_patches += 1
        if not patch_series_revision.processed:
            sync_patch_series_to_forge.send(patch_series_revision.id)
    with Session(engine) as session:
        relay.last_poll = time_now
        session.add(relay)
        session.commit()
    logger.info(f"Finished pulling patches for {relay_name}, pulled: {len(patches)}, new: {new_patches}")


def b4_am(outdir: Path, msg_id: str):
    redis_conn = redis.Redis(connection_pool=redis_pool)
    lock = redis.lock.Lock(redis_conn, "b4-lock", timeout=60)
    lock.acquire(blocking=True)
    try:
        subprocess.run(
            ["b4", "am", "--outdir", outdir, msg_id],
            timeout=60,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as err:
        logger.error("ERROR: Exception", err)
        logger.error("Stdout:", err.stdout.decode("utf-8"))
        logger.error("Stderr:", err.stderr.decode("utf-8"))
    finally:
        lock.release()


@dramatiq.actor(time_limit=60 * 1000)
def sync_patch_series_to_forge(patch_series_revision_id: int):
    with Session(engine) as session:
        patch_series_revision = session.get(PatchSeriesRevision, patch_series_revision_id)
        if not patch_series_revision:
            logger.error("Syncing patch series failed, patch series revision not found")
            return
        patch_series = patch_series_revision.patch_series
        patch_relay = patch_series_revision.patch_series.patch_relay
    relay_config = AppConfig.relay[patch_relay.name]
    forge_config = AppConfig.forge[relay_config.forge]
    now = get_database_time_now()
    logger.info(f"Syncing patch series ({patch_series.id}) v{patch_series_revision.version}: {patch_series.title}")
    with TemporaryDirectory() as tmp_dir:
        patch_parent_path = Path(tmp_dir)
        b4_am(patch_parent_path, patch_series_revision.msg_id)
        patch_file = next(patch_parent_path.glob("*.mbx"))
        cover_file = next(patch_parent_path.glob("*.cover"), None)
        description = parse_description_cover(cover_file) if cover_file else parse_description_mbx(patch_file)
        repo_path = GitRepoManager.get_path(relay_config.repo_url)
        repo_url = relay_config.repo_url
        url = urlparse(repo_url)
        repo_push_url = f"{url.scheme}://{forge_config.username}:{forge_config.token}@{url.hostname}/{url.path}"
        with GitRepo(
            repo_path,
            start_branch=relay_config.base_branch,
            repo_push_url=repo_push_url,
        ) as repo:
            repo.switch(patch_series.branch_name)
            try:
                repo.apply_patch_am(patch_file)
            except GitPatchDoesNotApplyError as err:
                logger.info(f"Patch series ({patch_series.id}) revision {patch_series_revision.version} doesn't apply")
                email = Email(AppConfig.email)
                email.send(
                    subject="[Reforged] Couldn't apply patch",
                    receivers=[patch_series.author_email],
                    text=f"Reforged has tried to sync you patch series to forge: {patch_series.title} v{patch_series_revision.version}, but couldn't apply patch series to {err.revision}:\n\n{err}",
                    reply_to=patch_series.author_email,
                )
                with Session(engine) as session:
                    patch_series_revision = session.get_one(PatchSeriesRevision, patch_series_revision.id)
                    patch_series_revision.processed = now
                    patch_series_revision.error = str(err)
                    session.add(patch_series_revision)
                    session.commit()
                return

            repo.push(patch_series.branch_name)
    forge = forge_registry[forge_config.forge_type](relay_config.repo_url, forge_config)
    forge_patch_series_data = {
        "title": patch_series_revision.patch_series.title,
        "body": description,
        "head": patch_series.branch_name,
        "base": relay_config.base_branch,
    }
    merge_request_url = forge.sync_patch_series(
        PatchSeriesData(**forge_patch_series_data), patch_series.merge_request_url
    )
    with Session(engine) as session:
        patch_series = session.get_one(PatchSeries, patch_series_revision.patch_series_id)
        if merge_request_url:
            patch_series.merge_request_url = merge_request_url
            session.add(patch_series)
        patch_series_revision = session.get_one(PatchSeriesRevision, patch_series_revision.id)
        patch_series_revision.synced = True
        patch_series_revision.processed = now
        session.add(patch_series_revision)
        session.commit()
        session.refresh(patch_series_revision)
        session.refresh(patch_series)
    logger.info(f"Synced patch series ({patch_series.id}) v{patch_series_revision.version}: {patch_series.title}")
