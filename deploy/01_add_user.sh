#!/bin/sh
#
# Setup the app user
#
# ----------------------------------------------------------------------------

set -x

sudo useradd -r -s /bin/false -d /opt/pywiki pywiki
sudo mkdir -p /opt/pywiki/data/attachments
sudo chown -R pywiki:pywiki /opt/pywiki


