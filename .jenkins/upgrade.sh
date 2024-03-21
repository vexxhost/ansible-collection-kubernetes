#! /bin/bash

set -xe

sudo apt update
sudo apt-get install -y git python3-pip docker.io

# Config Docker
groups
sudo usermod -aG docker $USER
if [ -d "/home/$USER/.docker" ]
  then
    sudo chown "$USER":"$USER" /home/"$USER"/.docker -R
    sudo chmod g+rwx "$HOME/.docker" -R
fi
sudo systemctl enable docker
sudo systemctl restart docker
sudo chmod 777 /var/run/docker.sock
#newgrp docker
docker -v
docker ps

pip install -r requirements.txt
sudo swapoff -a
sudo sysctl fs.inotify.max_user_instances=1280
sudo sysctl fs.inotify.max_user_watches=655360
PATH=$PATH:$HOME/.local/bin:$HOME/bin && molecule test -s cluster-upgrade
