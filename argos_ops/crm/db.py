"""Engine SQLAlchemy async + helper de session pour le CRM.

Utilise psycopg v3 (driver ``postgresql+psycopg``) en mode async. Engine
unique partagé par tous les agents — ne pas le recréer à chaque appel.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from argos_ops.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Engine SQLAlchemy async, créé lazy au premier appel."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.async_database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager qui commit en sortie propre, rollback en exception.

    Usage::

        async with session_scope() as session:
            await session.execute(...)
    """
    session = get_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """À appeler en shutdown propre (FastAPI lifespan, scripts CLI)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


__all__ = ["dispose_engine", "get_engine", "get_session_factory", "session_scope"]
