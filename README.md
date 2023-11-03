[![Coverage Status](https://coveralls.io/repos/SPSCommerce/redlock-py/badge.png)](https://coveralls.io/r/SPSCommerce/redlock-py)

redlock-py - Redis distributed locks in Python

This python lib implements the Redis-based distributed lock manager algorithm [described in this blog post](http://redis.io/topics/distlock).

To create a lock manager:

    conn = redis.Redis(
        host="localhost",
        port=6379
    )
    dlm = Redlock(connections=[conn], async_mode=False)

To acquire a lock:

    ok, my_lock = dlm.lock("my_resource_name", 1000)

Where the resource name is an unique identifier of what you are trying to lock and 1000 is the number of milliseconds for the validity time.

The returned ok flag is `False` if the lock was not acquired (you may try again), otherwise an namedtuple representing the lock is returned, having three fields:

* validity, an integer representing the number of milliseconds the lock will be valid.
* resource, the name of the locked resource as specified by the user.
* val, a random value which is used to safe reclaim the lock.

To release a lock:

    dlm.unlock(my_lock)

It is possible to setup the number of retries (by default 3) and the retry delay (by default 200 milliseconds) used to acquire the lock.

To extend your ownership of a lock that you already own:

    dlm.extend(my_lock, ttl)

where you want to extend the liftime of the lock by `ttl` milliseconds.  This returns
`True` if the extension succeeded and `False` if the lock had already expired.

**Disclaimer**: This code implements an algorithm which is currently a proposal, it was not formally analyzed. Make sure to understand how it works before using it in your production environments.

Further Reading:
http://redis.io/topics/distlock
http://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
http://antirez.com/news/101
https://medium.com/@talentdeficit/redlock-unsafe-at-any-time-40ceac109dbb#.uj9ffh96x
