# -*- coding: utf-8 -*-
import os
# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

from setuptools import setup, find_packages

README = '''
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
'''

setup(
    name='pyredlock',
    version='1.0.0',
    description='A Redis distributed lock implementation in Python',
    long_description=README,
    long_description_content_type='text/markdown',
    author='Adam Zhou',
    author_email='adamzhouisnothing@gmail.com',
    url='https://github.com/amazingchow/redlock-py',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "jsonschema==4.20.0",
        "loguru==0.7.2",
        "redis==5.0.1"
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    entry_points={
        'console_scripts': []
    }
)
