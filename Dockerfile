FROM ghcr.io/astral-sh/uv:0.12.17 AS uv

FROM maven:3.9.16-eclipse-temurin-21-noble

ARG PLANETILER_VERSION=0.10.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gir1.2-pango-1.0 \
        gir1.2-rsvg-2.0 \
        git \
        libcairo2-dev \
        libgirepository-2.0-dev \
        osmium-tool \
        pkg-config \
        python3 \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
RUN curl --fail --location \
        --output /opt/planetiler.jar \
        "https://github.com/onthegomap/planetiler/releases/download/v${PLANETILER_VERSION}/planetiler.jar"

COPY pyproject.toml uv.lock /tmp/project/
COPY tools/waymarked-sprite/pyproject.toml tools/waymarked-sprite/uv.lock /tmp/waymarked-sprite/
COPY tools/waymarked-sprite/LICENSE /usr/share/licenses/waymarked-sprite/COPYING
COPY tools/waymarked-sprite/NOTICE /usr/share/licenses/waymarked-sprite/NOTICE

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --project /tmp/project --locked --no-dev --no-install-project \
    && uv sync --project /tmp/waymarked-sprite --locked --no-dev --no-install-project --inexact

ENV PATH="/opt/venv/bin:${PATH}" \
    WAYMARKED_SPRITE_PYTHON=/opt/venv/bin/python \
    BUNDLED_PLANETILER_JAR=/opt/planetiler.jar \
    BUNDLED_PLANETILER_VERSION=${PLANETILER_VERSION}

WORKDIR /data
ENTRYPOINT ["python", "./scripts/generate.py"]
