# vstack -- single-image bundle of the Python library + all CLIs (vstack,
# vstack-mcp, vstack-api, vstack-config, vstack-upgrade, vstack-learn,
# vstack-analytics, plus the 34 per-pattern CLIs).
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
#
# Install path selection (the RUN step picks the first match):
#   1. A .whl file under `dist/` in the build context -- preferred. The
#      docker.yml workflow downloads the wheel artifact from release.yml
#      and drops it under dist/ before invoking buildx. This bypasses
#      the PyPI CDN-propagation race entirely.
#   2. A pinned VSTACK_VERSION build arg -- pip install from PyPI at the
#      pinned version. Used by manual local builds when no wheel exists
#      in the build context.
#   3. The latest PyPI version of valanistack[all] -- final fallback.

FROM python:3.13-slim AS runtime

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

# Always create dist/ in the image; copy any wheels the build context
# happens to have. When dist/ is absent in the context, the workflow
# pre-creates an empty one with a sentinel file so this COPY succeeds.
COPY dist/ /opt/vstack/dist/

ARG VSTACK_VERSION=""

RUN set -eux; \
    python -m pip install --upgrade pip; \
    WHEEL=$(ls /opt/vstack/dist/valanistack-*-py3-none-any.whl 2>/dev/null | head -n1 || true); \
    if [ -n "$WHEEL" ]; then \
        echo "Installing from local wheel: $WHEEL"; \
        pip install "${WHEEL}[all]"; \
    elif [ -n "$VSTACK_VERSION" ]; then \
        echo "Installing valanistack[all]==$VSTACK_VERSION from PyPI"; \
        pip install "valanistack[all]==$VSTACK_VERSION"; \
    else \
        echo "Installing latest valanistack[all] from PyPI"; \
        pip install "valanistack[all]"; \
    fi; \
    rm -rf /opt/vstack/dist; \
    mkdir -p "$VSTACK_HOME"; \
    chown -R vstack:vstack "$VSTACK_HOME" /opt/vstack

USER vstack

EXPOSE 8000

ENTRYPOINT ["tini", "--"]
CMD ["vstack-mcp", "serve"]
