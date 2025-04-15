import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Any

import redis
import redis.lock

from app.config import AppConfig

from .database import redis_pool

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class GitPatchDoesNotApplyError(Exception):
    def __init__(self, message: str, revision: str):
        super().__init__(message)
        self.revision = revision


class GitRepo:
    def __init__(
        self,
        path: Path,
        start_branch: str,
        repo_push_url: str,
        timeout: int | None = 120,
    ):
        self.path = path
        self.start_branch = start_branch
        self.repo_push_url = repo_push_url
        redis_conn = redis.Redis(connection_pool=redis_pool)
        self._lock = redis.lock.Lock(redis_conn, str(path), timeout=timeout)

    def __enter__(self) -> "GitRepo":
        self._lock.acquire(blocking=True, blocking_timeout=120)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is subprocess.CalledProcessError:
            logger.error(f"CalledProcessError: {exc_val}")
            logger.error(f"Stdout: {exc_val.stdout.decode('utf-8')}")
            logger.error(f"Stderr: {exc_val.stderr.decode('utf-8')}")
        if self._lock.locked():
            self._lock.release()

    def _git(self, *args: Any, **kwargs) -> subprocess.CompletedProcess:
        default_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "check": True,
            "timeout": 60,
        }
        result = subprocess.run(
            ["git", "-C", self.path, *args],
            env={"GIT_ADVICE": "0"},
            **{**default_kwargs, **kwargs},
        )
        return result

    def get_current_revision(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.decode("utf-8").strip()

    def _cleanup(self):
        self._git("am", "--abort", check=False)
        self._git("clean", "--force")

    def switch(self, branch: str):
        self._cleanup()
        self._git("fetch", "origin", self.start_branch)
        self._git("switch", "--discard-changes", "--force-create", branch, self.start_branch)

    def apply_patch_am(self, patch_file: Path):
        try:
            self._git("am", patch_file)
        except subprocess.CalledProcessError as e:
            if e.returncode == 128:
                raise GitPatchDoesNotApplyError(e.stderr.decode("utf-8"), self.get_current_revision())
            raise

    def push(self, branch: str):
        self._git("push", "--force", self.repo_push_url, branch)


class GitRepoManager:
    _instance: "GitRepoManager | None" = None

    def __new__(cls) -> None:
        if cls._instance is None:
            cls._instance = super().__new__(cls)

    @classmethod
    def register(cls, url: str):
        repo_path = cls.get_path(url)
        if not repo_path.exists():
            subprocess.run(["git", "clone", url, repo_path], check=True)

    @classmethod
    def get_path(cls, url: str) -> Path:
        repo_name = url.split("/")[-1].removesuffix(".git")
        unique_value = hashlib.md5(url.encode()).hexdigest()
        local_repo_name = f"{repo_name}_{unique_value[:4]}"
        return Path(AppConfig.git_repos_path) / local_repo_name
