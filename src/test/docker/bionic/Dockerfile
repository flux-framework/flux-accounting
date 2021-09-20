FROM fluxrm/flux-core:bionic-v0.28.0

ARG USER=flux
ARG UID=1000

# install pip
RUN sudo apt-get update
RUN sudo apt-get -qq install -y --no-install-recommends \
 python3-pip

# add configured user to image with sudo access:
RUN \
 if test "$USER" != "flux"; then  \
      sudo groupadd -g $UID $USER \
   && sudo useradd -g $USER -u $UID -d /home/$USER -m $USER \
   && sudo sh -c "printf \"$USER ALL= NOPASSWD: ALL\\n\" >> /etc/sudoers" \
   && sudo adduser $USER sudo ; \
 fi

USER $USER
WORKDIR /home/$USER
