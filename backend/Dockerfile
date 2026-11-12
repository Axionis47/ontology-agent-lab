FROM eclipse-temurin:21-jre-jammy AS java
FROM ghcr.io/astral-sh/uv:0.12.0 AS uv

FROM python:3.12-slim-bookworm AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JAVA_HOME=/opt/java/openjdk \
    OAK_JAVA=/opt/java/openjdk/bin/java \
    PORT=8000
ENV PATH="/app/.venv/bin:/opt/java/openjdk/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system oak \
    && useradd --system --gid oak --home-dir /app oak
COPY --from=java /opt/java/openjdk /opt/java/openjdk
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY oak ./oak
COPY migrations ./migrations
COPY scripts ./scripts
RUN java -version \
    && python -c "import owlready2" \
    && chown -R oak:oak /app

USER oak
EXPOSE 8000
CMD ["/bin/sh", "-c", "python -m oak.db && exec uvicorn oak.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
