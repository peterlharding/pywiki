#!/bin/sh
#
# -----------------------------------------------------------------------------

/opt/pywiki/.venv/bin/pip install --force-reinstall "python-jose[cryptography]>=3.3.0"
/opt/pywiki/.venv/bin/python -c "from jose import JWTError, jwt; print('OK')"


