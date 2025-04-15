import logging

import redis
import redis.lock
from sqlmodel import Session, select

from app.config import Config
from app.database import engine, redis_pool
from app.git import GitRepoManager
from app.models import PatchRelay

logger = logging.getLogger(__name__)


def initialize(config: Config) -> None:
    r = redis.Redis(connection_pool=redis_pool)
    logger.info("Initializing application")
    with redis.lock.Lock(r, "initialize", blocking=True):
        for relay_name, relay_config in config.relay.items():
            with Session(engine) as session:
                relay = session.exec(select(PatchRelay).where(PatchRelay.name == relay_name)).first()
                if not relay:
                    relay = PatchRelay(
                        name=relay_name,
                    )
                    session.add(relay)
                    session.commit()
                    session.refresh(relay)
            GitRepoManager.register(relay_config.repo_url)
    logger.info("Application initialized successfully")
