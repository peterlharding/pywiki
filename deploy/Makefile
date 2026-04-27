


DB_NAME         := $(shell grep DB_NAME      ../.env | sed 's/DB_NAME=//')
DIR_NAME        := $(shell grep DIR_NAME     ../.env | sed 's/DIR_NAME=//')
SERVICE_NAME    := $(shell grep SERVICE_NAME ../.env | sed 's/SERVICE_NAME=//')


# -----------------------------------------------------------------------------

chk-env:
	@echo "     DB_NAME |${DB_NAME}|"
	@echo "    DIR_NAME |${DIR_NAME}|"
	@echo "SERVICE_NAME |${SERVICE_NAME}|"


# -----------------------------------------------------------------------------

setup-venv:
	(cd ..; make venv; activate; make install)

setup-service:
	cp /opt/${DIR_NAME}/deploy/${SERVICE_NAME}.service /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable ${SERVICE_NAME}
	systemctl start  ${SERVICE_NAME}
	systemctl status ${SERVICE_NAME}


# -----------------------------------------------------------------------------

