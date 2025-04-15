import datetime
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import NotRequired, TypedDict

logger = logging.getLogger(__name__)

type PublicInboxQuery = str


class LeiMessage(TypedDict):
    blob: str
    c: list[list[str]]
    dt: str
    f: list[list[str]]
    m: str
    rt: str
    s: str
    t: list[list[str]]
    refs: NotRequired[list[str]]


def is_patch_series(lei_response: LeiMessage) -> bool:
    if lei_response.get("refs") is not None:
        return False
    if re.search(r"^\[PATCH.*\]", lei_response["s"]) is None:
        return False
    return True


@dataclass
class PatchData:
    title: str
    author: str
    author_email: str
    revision: int
    blob: str
    msg_id: str


def extract_patch_data(msg: LeiMessage) -> PatchData:
    subject_pattern = r"^\[PATCH( v(?P<version>\d+))?.*\]"
    subject = msg["s"]
    match = re.search(subject_pattern, subject)
    if not match:
        raise ValueError("Couldn't extract data")
    version = 1
    if val := match.groupdict().get("version"):
        version = int(val)
    title = subject[match.end() :].strip()
    return PatchData(
        title=title,
        author=msg["f"][0][0],
        author_email=msg["f"][0][1],
        revision=version,
        blob=msg["blob"],
        msg_id=msg["m"],
    )


class PublicInbox:
    def __init__(self, url: str, mailing_list_name: str) -> None:
        self.url = url
        self.mailing_list_name = mailing_list_name

    @classmethod
    def create_query(
        cls,
        subject_match: str | None = None,
        date_from: datetime.datetime | None = None,
        date_to: datetime.datetime | None = None,
    ) -> PublicInboxQuery:
        conditions: list[str] = []
        if subject_match:
            conditions.append(f"s:{subject_match}")
        if date_from or date_to:
            condition = "d:"
            if date_from:
                condition += f"{date_from.strftime('%Y-%m-%d')}"
            condition += ".."
            if date_to:
                condition += f"{date_to.strftime('%Y-%m-%d')}"
            conditions.append(condition)
        return " ".join(conditions)

    def fetch(self, query: PublicInboxQuery) -> list[LeiMessage]:
        try:
            result = subprocess.run(
                ["lei", "q", "-I", f"{self.url}/{self.mailing_list_name}", query],
                timeout=60,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return json.loads(result.stdout.decode("utf-8"))
        except subprocess.TimeoutExpired as err:
            logger.error("ERROR: Timeout expired", err)
        except subprocess.CalledProcessError as err:
            logger.error("ERROR: CalledProcessError", err)
            logger.error("Stdout:", err.stdout.decode("utf-8"))
            logger.error("Stderr:", err.stderr.decode("utf-8"))
        return []

    def get_patches(self, date_from: datetime.datetime | None = None) -> list[PatchData]:
        query = PublicInbox.create_query("PATCH", date_from=date_from)
        threads = self.fetch(query)
        filtered = [thread for thread in threads if thread and is_patch_series(thread)]
        return [extract_patch_data(msg) for msg in filtered]
