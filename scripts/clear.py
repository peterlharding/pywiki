#!/usr/bin/env python
#
# -----------------------------------------------------------------------------

import asyncio, os

os.chdir('/opt/pywiki')

from app.core.config import get_settings
from app.core.database import init_db, get_session_factory
from app.models.models import PageVersion
from sqlalchemy import update

s = get_settings()

init_db(s.database_url)

async def clear():
    sf = get_session_factory()
    async with sf() as db:
        await db.execute(update(PageVersion).values(rendered=None))
        await db.commit()
    print('done')

asyncio.run(clear())

