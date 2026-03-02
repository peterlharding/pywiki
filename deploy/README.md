# PyWiki — Server Deployment

Target: **https://expanse.performiq.com**

| Service | External URL | Internal address |
|---------|-------------|------------------|
| PyWiki  | `https://expanse.performiq.com` | `127.0.0.1:8700` |

---

## 1. Create system user and directories

```bash
sudo useradd -r -s /bin/false -d /opt/pywiki pywiki
sudo mkdir -p /opt/pywiki/data/attachments
sudo chown -R pywiki:pywiki /opt/pywiki
```

---

## 2. Deploy application code

Clone from the repository or rsync from the dev machine:

```bash
# Option A — git clone
sudo -u pywiki git clone <repo-url> /opt/pywiki

# Option B — rsync from dev
rsync -av \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='data/' \
    --exclude='.git' \
    ./ pywiki@<server>:/opt/pywiki/
```

---

## 3. Create virtual environment and install dependencies

The venv **must not** inherit system site-packages — some distributions ship
a stale Python 2 `jose` package globally that will shadow `python-jose` and
cause a `SyntaxError` at startup.

```bash
sudo -u pywiki bash -c "
  cd /opt/pywiki
  python3 -m venv --clear .venv
  .venv/bin/pip install --upgrade pip setuptools wheel
  .venv/bin/pip install -r deploy/requirements.txt
"
```

> If `uv` is available on the server it is faster:
> ```bash
> sudo -u pywiki bash -c "
>   cd /opt/pywiki
>   python3 -m venv --clear .venv
>   uv pip install -r deploy/requirements.txt --python .venv/bin/python
> "
> ```

**Verify the install is clean before continuing:**

```bash
sudo -u pywiki /opt/pywiki/.venv/bin/python -c "
from jose import JWTError, jwt; print('jose OK')
from fastapi import FastAPI; print('fastapi OK')
import asyncpg; print('asyncpg OK')
"
```

If `jose` reports a `SyntaxError`, a stale system package is shadowing it:

```bash
# Remove the offending system package
sudo pip3 uninstall jose

# Re-install the correct one into the venv
sudo -u pywiki /opt/pywiki/.venv/bin/pip install --force-reinstall "python-jose[cryptography]>=3.3.0"
```

---

## 4. Configure environment

```bash
sudo cp /opt/pywiki/deploy/.env.example /opt/pywiki/.env
sudo nano /opt/pywiki/.env
```

Key values to set:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string — set the real password |
| `SECRET_KEY` | Generate: `python3 -c "import secrets; print(secrets.token_hex(64))"` |
| `BASE_URL` | `https://expanse.performiq.com` |
| `ATTACHMENT_ROOT` | `/opt/pywiki/data/attachments` |
| `SMTP_*` | Brevo (or other relay) credentials |
| `ALLOW_REGISTRATION` | `true` until first admin is created, then `false` |

Secure the file:

```bash
sudo chown pywiki:pywiki /opt/pywiki/.env
sudo chmod 600 /opt/pywiki/.env
```

---

## 5. Create the PostgreSQL database and user

```bash
sudo -u postgres psql <<'SQL'
CREATE USER pywiki WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE pywiki OWNER pywiki;
GRANT ALL PRIVILEGES ON DATABASE pywiki TO pywiki;
SQL
```

---

## 6. Run database migrations

```bash
sudo -u pywiki bash -c "
  cd /opt/pywiki
  PYTHONPATH=. .venv/bin/alembic upgrade head
"
```

---

## 7. Install and start the systemd service

```bash
sudo cp /opt/pywiki/deploy/pywiki.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pywiki
sudo systemctl start  pywiki
sudo systemctl status pywiki
```

Check it is listening:

```bash
curl -s http://127.0.0.1:8700/ | head -5
```

---

## 8. Obtain SSL certificate (if not already present)

```bash
# Ensure port 80 is open and nginx is serving the ACME challenge location
sudo certbot certonly --nginx -d expanse.performiq.com
```

> If nginx is not yet installed, use the standalone mode instead:
> ```bash
> sudo certbot certonly --standalone -d expanse.performiq.com
> ```

---

## 9. Install nginx config

```bash
sudo cp /opt/pywiki/deploy/nginx-pywiki.conf \
    /etc/nginx/sites-available/expanse.performiq.com
sudo ln -s /etc/nginx/sites-available/expanse.performiq.com \
    /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 10. Open firewall ports

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

Port 8700 should **not** be exposed externally — nginx proxies to it on localhost.

---

## 11. Bootstrap first admin user

Registration is enabled by default (`ALLOW_REGISTRATION=true`).

1. Open `https://expanse.performiq.com` and register your admin account.
2. Promote it to admin via psql:

```bash
psql -h 127.0.0.1 -U pywiki -d pywiki \
  -c "UPDATE users SET is_admin = TRUE WHERE username = 'your-username';"
```

3. Once the admin account is set up, **disable public registration**:

In `/opt/pywiki/.env`:
```
ALLOW_REGISTRATION=false
```

Then restart:

```bash
sudo systemctl restart pywiki
```

---

## Useful commands

```bash
# View live logs
sudo journalctl -u pywiki -f

# Restart after a code update
sudo systemctl restart pywiki

# Run migrations after a code update
sudo -u pywiki bash -c "cd /opt/pywiki && PYTHONPATH=. .venv/bin/alembic upgrade head"

# Pull latest code (if deployed via git)
sudo -u pywiki bash -c "cd /opt/pywiki && git pull"
sudo systemctl restart pywiki

# Check service health
sudo systemctl status pywiki
curl -s https://expanse.performiq.com/special/status | head -20
```

---

## Updating the application

```bash
# 1. Deploy new code (rsync or git pull)
sudo -u pywiki bash -c "cd /opt/pywiki && git pull"

# 2. Install any new dependencies
sudo -u pywiki bash -c "cd /opt/pywiki && .venv/bin/pip install -e ."

# 3. Run any new migrations
sudo -u pywiki bash -c "cd /opt/pywiki && PYTHONPATH=. .venv/bin/alembic upgrade head"

# 4. Restart the service
sudo systemctl restart pywiki
```
