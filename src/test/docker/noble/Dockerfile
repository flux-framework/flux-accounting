FROM fluxrm/flux-core:noble

ARG USER=flux
ARG UID=1000

# Install necessary tools
USER root
RUN apt-get update && \
    apt-get install -y sudo passwd

# add configured user to image with sudo access:
RUN \
 if test "$USER" != "flux"; then  \
      groupadd -g $UID $USER \
    && sudo useradd -g $USER -u $UID -d /home/$USER -m $USER \
    && sh -c "printf \"$USER ALL= NOPASSWD: ALL\\n\" >> /etc/sudoers" \
    && sudo adduser $USER sudo ; \
 fi

USER $USER
WORKDIR /home/$USER
