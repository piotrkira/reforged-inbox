from datetime import datetime
from pathlib import Path


# The main purpose of this function is to get rid of the listing of changed
# files.
def parse_description_mbx(mbx_file: Path) -> str:
    lines: list[str]
    description_lines: list[str] = []
    with open(mbx_file, "r") as file:
        lines = file.readlines()

    for line in lines:
        if line.startswith("---"):
            break
        description_lines.append(line.strip())
    return "\n".join(description_lines)


def parse_description_cover(cover_file: Path) -> str:
    lines: list[str]
    description_lines: list[str] = []
    with open(cover_file, "r") as file:
        lines = file.readlines()

    for line in lines:
        if line.startswith("  "):
            if len(description_lines) > 2:
                description_lines = description_lines[:-2]
            break
        description_lines.append(line.strip())
    return "\n".join(description_lines)


def timesince(date: datetime | None, now: datetime = datetime.now()) -> str:
    if date is None:
        return "unknown"
    delta = now - date
    if delta.days > 0:
        return f"{delta.days} days ago"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600} hours ago"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60} minutes ago"
    else:
        return "just now"
