# -*- coding: utf-8 -*-
import asyncio
import jsonschema
import redis
import redis.asyncio as aio_redis
import redis.exceptions as redis_exceptions

from loguru import logger as loguru_logger
from typing import Any, Dict, Optional


class Singleton(type):
    
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class RedisClientSetupException(Exception):
    pass


class AioRedisClient(metaclass=Singleton):
    """Redis client wrapper class."""

    CLIENT_CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string"},
            "db": {"type": "number"},
            "password": {"type": "string"},
            "socket_timeout": {"type": "number"},
            "socket_connect_timeout": {"type": "number"}
        },
        "required": [
            "endpoint",
            "db",
            "password",
            # the timeout for r/w from/to the socket
            "socket_timeout",
            # the timeout for socket connection
            "socket_connect_timeout"
        ],
    }
    
    def __init__(self, client_conf: Dict[str, Any], io_loop: Optional[asyncio.BaseEventLoop] = None) -> None:
        """
        Initialize the AioRedisClient.

        Args:
            client_conf (Dict[str, Any]): The configuration for the Redis client.
            io_loop (Optional[asyncio.BaseEventLoop], optional): The event loop to use for asynchronous operations. Defaults to None.
        
        Raises:
            RedisClientSetupException: If the provided Redis client configuration is invalid.
        """
        self._conn: Optional[aio_redis.Redis] = None

        if not self.validate_client_config(client_conf):
            raise RedisClientSetupException("Please provide valid redis config file.")

        host, port = client_conf["endpoint"].split(":")[0], int(client_conf["endpoint"].split(":")[1])
        self._srv_endpoint = client_conf["endpoint"]
        if io_loop is not None:
            self._conn = aio_redis.Redis(
                host=host,
                port=port,
                db=client_conf["db"],
                password=client_conf["password"],
                socket_timeout=client_conf["socket_timeout"],
                socket_connect_timeout=client_conf["socket_connect_timeout"],
                loop=io_loop
            )
        else:
            self._conn = aio_redis.Redis(
                host=host,
                port=port,
                db=client_conf["db"],
                password=client_conf["password"],
                socket_timeout=client_conf["socket_timeout"],
                socket_connect_timeout=client_conf["socket_connect_timeout"]
            )

    @classmethod
    def validate_client_config(cls, conf: Dict[str, Any]) -> bool:
        """
        Validate the Redis client configuration.

        Args:
            conf (Dict[str, Any]): The Redis client configuration.

        Returns:
            bool: True if the configuration is valid, False otherwise.
        """
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=cls.CLIENT_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError:
            loguru_logger.error(f"Invalid redis config:{conf}.")
        finally:
            return valid

    async def is_connected(self) -> bool:
        """
        Check if the Redis client is connected to the server.

        Returns:
            bool: True if connected, False otherwise.
        """
        connected = False
        try:
            if self._conn is not None:
                connected = await self._conn.ping()
        except redis_exceptions.RedisError as exc:
            loguru_logger.error(f"Redis connection error:{exc}.")
        finally:
            return connected

    def get_connection(self) -> Optional[aio_redis.Redis]:
        """
        Get the Redis connection.

        Returns:
            Optional[aio_redis.Redis]: The Redis connection object.
        """
        return self._conn

    async def close(self):
        """
        Close the Redis connection.
        """
        if self._conn is not None:
            await self._conn.aclose()


class RedisClient(metaclass=Singleton):
    """Redis client wrapper class."""

    CLIENT_CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string"},
            "db": {"type": "number"},
            "password": {"type": "string"},
            "socket_timeout": {"type": "number"},
            "socket_connect_timeout": {"type": "number"}
        },
        "required": [
            "endpoint",
            "db",
            "password",
            # the timeout for r/w from/to the socket
            "socket_timeout",
            # the timeout for socket connection
            "socket_connect_timeout"
        ],
    }
    
    def __init__(self, client_conf: Dict[str, Any]) -> None:
        """
        Initialize the RedisClient.

        Args:
            client_conf (Dict[str, Any]): The configuration for the Redis client.
            io_loop (Optional[asyncio.BaseEventLoop], optional): The event loop to use for asynchronous operations. Defaults to None.
        
        Raises:
            RedisClientSetupException: If the provided Redis client configuration is invalid.
        """
        self._conn: Optional[redis.Redis] = None

        if not self.validate_client_config(client_conf):
            raise RedisClientSetupException("Please provide valid redis config file.")

        host, port = client_conf["endpoint"].split(":")[0], int(client_conf["endpoint"].split(":")[1])
        self._srv_endpoint = client_conf["endpoint"]
        self._conn = redis.Redis(
            host=host,
            port=port,
            db=client_conf["db"],
            password=client_conf["password"],
            socket_timeout=client_conf["socket_timeout"],
            socket_connect_timeout=client_conf["socket_connect_timeout"]
        )

    @classmethod
    def validate_client_config(cls, conf: Dict[str, Any]) -> bool:
        """
        Validate the Redis client configuration.

        Args:
            conf (Dict[str, Any]): The Redis client configuration.

        Returns:
            bool: True if the configuration is valid, False otherwise.
        """
        valid = False
        try:
            jsonschema.validate(instance=conf, schema=cls.CLIENT_CONFIG_SCHEMA)
            valid = True
        except jsonschema.ValidationError:
            loguru_logger.error(f"Invalid redis config:{conf}.")
        finally:
            return valid

    def is_connected(self) -> bool:
        """
        Check if the Redis client is connected to the server.

        Returns:
            bool: True if connected, False otherwise.
        """
        connected = False
        try:
            if self._conn is not None:
                connected = self._conn.ping()
        except redis_exceptions.RedisError as exc:
            loguru_logger.error(f"Redis connection error:{exc}.")
        finally:
            return connected

    def get_connection(self) -> Optional[redis.Redis]:
        """
        Get the Redis connection.

        Returns:
            Optional[redis.Redis]: The Redis connection object.
        """
        return self._conn

    def close(self):
        """
        Close the Redis connection.
        """
        if self._conn is not None:
            self._conn.close()
