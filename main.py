import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

import app.actors
import app.routers
from app.config import AppConfig
from app.deps import initialize

logger = logging.getLogger(__name__)


def main():
    initialize(AppConfig)
    scheduler = BlockingScheduler()
    for relay_name, relay in AppConfig.relay.items():
        scheduler.add_job(
            app.actors.pull_patches.send,
            IntervalTrigger(minutes=relay.pooling_interval),
            args=[relay_name],
        )
    try:
        scheduler.start()
    except Exception as err:
        logging.error("ERROR: Exception occurred in main", err)


fast_api_app = FastAPI()
fast_api_app.include_router(app.routers.api_router)

if __name__ == "__main__":
    logger.info("Starting the application")
    main()
