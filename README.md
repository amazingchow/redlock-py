
pyredlock - A Redis distributed lock implementation in Python

This python lib implements the Redis-based distributed lock manager algorithm [described in this blog post](https://redis.io/docs/manual/patterns/distributed-locks/).

### How to use it?

To create a lock manager:

```python
from pyredlock import RedisClient
from pyredlock import Redlock, Lock

...
client = RedisClient(client_conf={
    "endpoint": "localhost:6379",
    "password": "your_redis_password",
    "db": 0,
    "socket_timeout": 0.5,
    "socket_connect_timeout": 0.25
})
lock_mgr = Redlock(connections=[client.get_connection()], async_mode=False)
...
```

To acquire a lock:

```python
...
success, my_lock = lock_mgr.lock("my_resource_name", 1000)
...
```

To release a lock:

```python
...
lock_mgr.unlock(my_lock)
...
```

To extend your ownership of a lock that you already own:

```python
...
lock_mgr.extend(my_lock, 1000)
...
```

**Disclaimer**: This implementation is currently a proposal, it was not formally analyzed. Make sure to understand how it works before using it in your production environments.

### Further Readings

* https://redis.io/docs/manual/patterns/distributed-locks/
* https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
* http://antirez.com/news/101
* https://mp.weixin.qq.com/s/O8o31rRBVL1DwK-JfmurRw
