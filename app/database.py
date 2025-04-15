import redis
from sqlmodel import create_engine

from app.config import AppConfig

connect_args = {}
if AppConfig.database.connection_url.startswith("sqlite:///"):
    connect_args["check_same_thread"] = False

engine = create_engine(AppConfig.database.connection_url, echo=False, connect_args=connect_args)

redis_pool = redis.ConnectionPool(
    host=AppConfig.redis.host, password=AppConfig.redis.password, port=AppConfig.redis.port, db=AppConfig.redis.db
)
