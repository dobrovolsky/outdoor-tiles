FROM ghcr.io/astral-sh/uv:0.12.17 AS uv

FROM maven:3.9.16-eclipse-temurin-21-noble

ARG PLANETILER_VERSION=0.10.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends osmium-tool python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock /tmp/project/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --project /tmp/project --locked --no-dev --no-install-project \
    && curl --fail --location \
        --output /opt/planetiler.jar \
        "https://github.com/onthegomap/planetiler/releases/download/v${PLANETILER_VERSION}/planetiler.jar"

ENV PATH="/opt/venv/bin:${PATH}" \
    BUNDLED_PLANETILER_JAR=/opt/planetiler.jar \
    BUNDLED_PLANETILER_VERSION=${PLANETILER_VERSION}

WORKDIR /data
ENTRYPOINT ["python", "./scripts/generate.py"]
