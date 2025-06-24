import redis
from sqlmodel import create_engine, text

from app.config import AppConfig

connect_args = {}
is_sqlite = AppConfig.database.connection_url.startswith("sqlite://")
if is_sqlite:
    connect_args["check_same_thread"] = False

engine = create_engine(AppConfig.database.connection_url, echo=False, connect_args=connect_args)

if is_sqlite:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.commit()

redis_pool = redis.ConnectionPool(
    host=AppConfig.redis.host, password=AppConfig.redis.password, port=AppConfig.redis.port, db=AppConfig.redis.db
)
