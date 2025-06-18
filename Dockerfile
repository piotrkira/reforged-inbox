FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git b4 lei
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"ROM

RUN mkdir /repos /app /data
ENV REFORGED_REPOS_PATH="/repos"

COPY pyproject.toml uv.lock /app
WORKDIR /app
RUN uv sync --locked
COPY . /app
