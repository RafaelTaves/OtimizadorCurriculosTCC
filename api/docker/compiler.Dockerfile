FROM python:3.14-slim-bookworm
ARG TECTONIC_VERSION=0.15.0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates fontconfig libharfbuzz0b libgraphite2-3 libssl3 \
    && curl --fail --location --retry 3 "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" -o /tmp/tectonic.tar.gz \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && rm /tmp/tectonic.tar.gz && rm -rf /var/lib/apt/lists/*
ENV HOME=/home/compiler
ENV TECTONIC_UNTRUSTED_MODE=1
RUN useradd --uid 10001 --create-home compiler && mkdir /work && chown compiler:compiler /work
COPY app/templates/resume-v1.tex /opt/template.tex
COPY docker/warm_cache.py /opt/warm_cache.py
COPY docker/compile.py /opt/compile.py
USER compiler
WORKDIR /work
# Build-time network only: prefetch all packages and exercise the complete template with accents.
RUN python /opt/warm_cache.py
ENTRYPOINT ["python", "/opt/compile.py"]
