FROM fluxrm/flux-core:bookworm

LABEL maintainer="Vanessasaurus <@vsoch>"

# Match the default user id for a single system so we aren't root
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
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
        curl

# Assuming installing to /usr/local
ENV LD_LIBRARY_PATH=/usr/lib:/usr/local/lib      
ENV PATH=$PATH:/usr/local/go/bin:/home/vscode/go/bin

# extra interactive utilities
RUN apt-get update \
 && apt-get -qq install -y --no-install-recommends \
    fd-find \
    less \
    bats \
    ripgrep

# Add the group and user that match our ids
RUN groupadd -g ${USER_GID} ${USERNAME} && \
    adduser --disabled-password --uid ${USER_UID} --gid ${USER_GID} --gecos "" ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers
USER $USERNAME
