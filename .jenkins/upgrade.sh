#!/bin/bash

set +ex

sudo apt-get install -y git python3-pip docker.io
sudo chown $USER /var/run/docker.sock
pip install -r requirements.txt
sudo swapoff -a
sudo sysctl fs.inotify.max_user_watches=524288
PATH=$PATH:$HOME/.local/bin:$HOME/bin && molecule test -s cluster-upgrade
