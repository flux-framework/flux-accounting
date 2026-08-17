FROM fluxrm/flux-core:bookworm

LABEL maintainer="Vanessasaurus <@vsoch>"

# Match the default user id for a single system so we aren't root
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
ARG CLAUDE_CODE_VERSION=latest
ENV USERNAME=${USERNAME}
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}
USER root

# Install extra buildrequires for flux-sched:
RUN sudo apt-get update
RUN sudo apt-get -qq install -y --no-install-recommends \
        libboost-graph-dev \
        libboost-system-dev \
        libboost-filesystem-dev \
        libboost-regex-dev \
        python3-yaml \
        libyaml-cpp-dev \
        libedit-dev \
        ninja-build \
        curl \
        nodejs \
        npm \
        iptables \
        ipset \
        iproute2 \
        dnsutils \
        aggregate

# Assuming installing to /usr/local
ENV LD_LIBRARY_PATH=/usr/lib:/usr/local/lib

RUN curl -s -L https://github.com/Kitware/CMake/releases/download/v3.26.4/cmake-3.26.4-linux-$(uname -m).sh > cmake.sh ;\
    sudo bash cmake.sh --prefix=/usr/local --skip-license ;\
    rm cmake.sh


# extra interactive utilities
RUN apt-get update \
 && apt-get -qq install -y --no-install-recommends \
    fd-find \
    less \
    bats \
    ripgrep \
    sqlite3 \
    python3-pip

RUN python3 -m pip install --break-system-packages 'black~=26.1'

# Install Claude
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Add the group and user that match our ids
RUN groupadd -g ${USER_GID} ${USERNAME} && \
    adduser --disabled-password --uid ${USER_UID} --gid ${USER_GID} --gecos "" ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers
USER $USERNAME

# Load site-specific configuration (endpoint, models, token) if the developer
# has created one. See .devcontainer/claude/claude.env.example
RUN printf '%s\n' \
    '' \
    '# Load site-specific Claude Code configuration, if present.' \
    'if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -f "${CLAUDE_ENV_FILE}" ]; then' \
    '    . "${CLAUDE_ENV_FILE}"' \
    'fi' \
    >> /home/vscode/.bashrc

# Copy and set up firewall script
RUN mkdir -p /home/vscode/.claude/
COPY .devcontainer/claude/init-firewall.sh /usr/local/bin/
COPY --chown=${USER_UID}:${USER_GID} .devcontainer/claude/settings.json /home/vscode/.claude/settings.json
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh && \
  echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/${USERNAME}-firewall && \
  chmod 0440 /etc/sudoers.d/${USERNAME}-firewall
USER $USERNAME
