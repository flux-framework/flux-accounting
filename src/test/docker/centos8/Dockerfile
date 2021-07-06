FROM fluxrm/flux-core:centos8-v0.28.0

ARG USER=flux
ARG UID=1000

# Add configured user to image with sudo access:
#
RUN \
 if test "$USER" != "flux"; then  \
      sudo groupadd -g $UID $USER \
   && sudo useradd -g $USER -u $UID -d /home/$USER -m $USER \
   && sudo sh -c "printf \"$USER ALL= NOPASSWD: ALL\\n\" >> /etc/sudoers" \
   && sudo usermod -G wheel $USER; \
 fi

RUN \
 sudo pip3 install pandas==0.24.1

USER $USER
WORKDIR /home/$USER
