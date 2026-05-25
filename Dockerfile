# vstack -- single-image bundle of the Python library + all CLIs (vstack-mcp,
# vstack-api, vstack-config, vstack-upgrade, plus the 34 per-pattern CLIs).
#
# The image is multi-arch by default (the docker.yml workflow builds for
# linux/amd64 and linux/arm64). It is intended as a portable runtime; the
# library itself stays installable via pip for users who don't want a
# container.
#
# Default CMD runs the MCP server over stdio. Override at run-time:
#   docker run --rm -i ghcr.io/valani9/vstack:latest                     # vstack-mcp serve
#   docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY=... ghcr.io/valani9/vstack:latest \
#       vstack-api serve --host 0.0.0.0 --port 8000
#   docker run --rm ghcr.io/valani9/vstack:latest vstack --help

FROM python:3.13-slim AS runtime

# Tools installed via uv are reproducible, fast, and don't drag in pip's
# resolver. We still keep `pip` available for `pip install` of plugins
# at runtime (e.g. user-installed Anthropic/OpenAI extras).
RUN useradd --create-home --uid 1000 vstack \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tini \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VSTACK_HOME=/var/lib/vstack

WORKDIR /opt/vstack

# Install vstack with every optional extra so the resulting image
# supports MCP stdio + REST API + Anthropic / OpenAI / Ollama clients
# out of the box. Pinning to the major version makes the docker tag
# predictable; the CI workflow rebuilds the image on every release.
ARG VSTACK_VERSION
RUN python -m pip install --upgrade pip \
    && if [ -n "$VSTACK_VERSION" ]; then \
         pip install "valanistack[all]==$VSTACK_VERSION"; \
       else \
         pip install "valanistack[all]"; \
       fi \
    && mkdir -p "$VSTACK_HOME" && chown -R vstack:vstack "$VSTACK_HOME" /opt/vstack

USER vstack

# Expose the API port for `vstack-api serve --host 0.0.0.0`.
EXPOSE 8000

# tini reaps zombie children cleanly when running short-lived CLI
# invocations or when uvicorn is signaled.
ENTRYPOINT ["tini", "--"]
CMD ["vstack-mcp", "serve"]
