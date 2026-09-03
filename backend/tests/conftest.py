from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def flow_manager():
    fm = MagicMock()
    fm.state = {}
    return fm


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value="UPDATE 0")
    return pool


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    redis.zrange = AsyncMock(return_value=[])
    redis.hmget = AsyncMock(return_value=[])
    redis.zinterstore = AsyncMock()
    redis.ttl = AsyncMock(return_value=900)
    redis.expire = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    return redis


def make_row(**kwargs):
    """Minimal asyncpg-record stand-in: supports record["key"] and truthiness."""
    row = MagicMock()
    row.__getitem__ = lambda self, k: kwargs[k]
    row.__bool__ = lambda self: bool(kwargs)
    return row