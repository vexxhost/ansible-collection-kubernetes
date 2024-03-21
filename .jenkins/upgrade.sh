#! /bin/bash

sudo apt-get install -y git python3-pip docker.io
sudo groupadd docker
sudo usermod -aG docker $USER
sudo systemctl restart docker
sudo pip install -r requirements.txt
sudo swapoff -a
sudo sysctl fs.inotify.max_user_watches=524288
molecule test -s cluster-upgrade
