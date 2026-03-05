#!/bin/sh
#
# Note: Adjust the port as required here and in ../.env BASE_URL
#
# -----------------------------------------------------------------------------

set -x

cp /opt/pywiki/deploy/pywiki.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable pywiki
systemctl start  pywiki
systemctl status pywiki



