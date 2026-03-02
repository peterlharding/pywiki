
setup-xxx:
	(cd ..; make venv; activate; make install)

setup-service:
	cp /opt/pywiki/deploy/pywiki.service /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable pywiki
	systemctl start  pywiki
	systemctl status pywiki

