#!/usr/bin/env python
#
# -------------------------------------------------------------------------------

import asyncio
from app.core.config import get_settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from app.models import User
 
async def check():
    s = get_settings()
    print("DATABASE_URL:", s.database_url)
    engine = create_async_engine(s.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"  id={u.id} username={u.username} is_admin={u.is_admin} is_active={u.is_active}")
    await engine.dispose()
 
asyncio.run(check())
