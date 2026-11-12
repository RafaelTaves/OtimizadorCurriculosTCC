FROM python:3.14-slim-bookworm AS compiler
ARG TECTONIC_VERSION=0.15.0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates fontconfig libharfbuzz0b libgraphite2-3 libssl3 \
    && curl --fail --location --retry 3 "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" -o /tmp/tectonic.tar.gz \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && rm /tmp/tectonic.tar.gz
ENV HOME=/home/compiler TECTONIC_UNTRUSTED_MODE=1
RUN mkdir -p /home/compiler /work
WORKDIR /work
COPY app/templates/resume-v1.tex /opt/template.tex
COPY docker/warm_cache.py /opt/warm_cache.py
RUN python /opt/warm_cache.py
COPY docker/prepare-jail.py /opt/prepare-jail.py
RUN python /opt/prepare-jail.py

FROM python:3.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends libseccomp2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
RUN uv sync --frozen --no-dev
COPY --from=compiler /opt/tex-root /opt/tex-root
COPY docker/tex-sandbox.py /opt/tex-sandbox.py
COPY docker/railway-worker.py /opt/railway-worker.py
COPY docker/check_sandbox.py /opt/check_sandbox.py
ENV PATH="/app/.venv/bin:$PATH" COMPILER_BACKEND=sandbox PYTHONUNBUFFERED=1
# Root is necessary only for the launcher to chroot and drop UID. TeX runs as 10002.
USER root
CMD ["python", "/opt/railway-worker.py", "--lane", "pdf"]
