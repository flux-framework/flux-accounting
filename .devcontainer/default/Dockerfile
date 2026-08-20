# Flux developer environment. If Flux ever publishes its own devcontainer
# images, this FROM is the only line that needs to change.
FROM ghcr.io/vsoch/devcontainer/images/flux:latest

LABEL maintainer="Vanessasaurus <@vsoch>"

USER root

# flux-accounting specific dependencies. libsqlite3-dev is already in the base
# image; this is the command line client, plus the formatter CI checks against.
RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        sqlite3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m pip install --break-system-packages 'black~=26.1'

USER vscode
