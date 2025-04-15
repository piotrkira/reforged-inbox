import logging
import os
import tomllib

from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ],
)


class RedisConfig(BaseModel):
    host: str = Field(default=os.getenv("REDIS_HOST", "localhost"))
    password: str | None = Field(default=None)
    port: int = Field(default=6379)
    db: int = Field(default=0)


class DatabaseConfig(BaseModel):
    connection_url: str = Field(default=os.getenv("DB_CONNECTION_URL", "sqlite:///reforged.db"))


class ForgeConfig(BaseModel):
    forge_type: str
    username: str
    token: str


class RelayConfig(BaseModel):
    forge: str
    mailing_list: str
    public_inbox_url: str
    base_branch: str
    pooling_interval: int = Field(ge=1)
    repo_url: str


class EmailConfig(BaseModel):
    host: str
    port: int = Field(default=587)
    starttls: bool = Field(default=True)
    username: str
    password: str
    email: EmailStr
    name: str | None = None


class Config(BaseModel):
    database: DatabaseConfig = Field(default=DatabaseConfig())
    redis: RedisConfig = Field(default=RedisConfig())
    forge: dict[str, ForgeConfig]
    relay: dict[str, RelayConfig]
    email: EmailConfig
    git_repos_path: str = Field(default=os.getenv("REFORGED_REPOS_PATH", "./repos"))


AppConfig: Config
with open("reforged.toml", "rb") as f:
    data = tomllib.load(f)
    AppConfig = Config.model_validate(data)
