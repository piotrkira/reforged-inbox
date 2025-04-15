import logging
from abc import ABC, abstractmethod
from typing import TypedDict

from github import Github

from .config import ForgeConfig

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ForgeData:
    title: str
    body: str
    merge_request_id: int


class ForgeDataGithub(ForgeData):
    pull_request_id: int
    head: str
    base: str


class PatchSeriesData(TypedDict):
    title: str
    body: str
    head: str
    base: str


class Forge(ABC):
    def __init__(self, repo_url: str, config: ForgeConfig):
        self.repo_url = repo_url
        self.config = config

    @abstractmethod
    def sync_patch_series(self, patch_series_data: PatchSeriesData, merge_request_url: str | None = None) -> str | None:
        pass


class GithubForge(Forge):
    def __init__(self, repo_url: str, config: ForgeConfig):
        repo_name = repo_url.split("/")[-1].removesuffix(".git")
        owner_name = repo_url.split("/")[-2]
        self.repo = f"{owner_name}/{repo_name}"
        self.config = config

    def sync_patch_series(self, patch_series_data: PatchSeriesData, merge_request_url: str | None = None) -> str | None:
        g = Github(self.config.token)
        repo = g.get_repo(self.repo)

        if merge_request_url:
            pull_request_number = int(merge_request_url.split("/")[-1])
            if pull_request := repo.get_pull(pull_request_number):
                pull_request.edit(title=patch_series_data["title"], body=patch_series_data["body"])
                return

        pull_request = repo.create_pull(
            title=patch_series_data["title"],
            body=patch_series_data["body"],
            head=patch_series_data["head"],
            base=patch_series_data["base"],
        )
        return pull_request.html_url


forge_registry: dict[str, type[Forge]] = {"github": GithubForge}
