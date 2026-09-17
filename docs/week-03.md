# Week 03 — Redis Caching and Cache Design

## Objective

The goal of this week is to understand how caching changes the performance and failure behavior of a backend system.

The system evolves from:

```text
Locust → FastAPI → PostgreSQL
```

to:

```text
                 ┌── Redis
                 │
Locust → FastAPI ┤
                 │
                 └── PostgreSQL
```

The main topics are:

- Cache-aside
- Cache hits and misses
- Cache hit ratio
- TTL
- Cache invalidation
- Stale data
- Cache warming
- Cache stampede
- Graceful degradation
- Cascading failures
- Read-heavy workload optimization

The key question is:

> When does caching actually help, and what new problems does it introduce?

---

## 1. Test Environment

Application:

- Python
- FastAPI
- Uvicorn

Persistent storage:

- PostgreSQL

Cache:

- Redis

Load generator:

- Locust

Primary endpoint:

```text
GET /urls/{short_code}
```

The endpoint retrieves the original URL corresponding to a short code.

---

## 2. Baseline Architecture

Before Redis:

```text
Client
   |
   v
FastAPI
   |
   v
PostgreSQL
```

Every URL lookup reaches PostgreSQL.

For a read-heavy workload, repeated requests for the same URLs generate repeated database queries.

---

## 3. Redis Architecture

After introducing Redis:

```text
Client
   |
   v
FastAPI
   |
   v
Redis
 |   \
 |    \ cache miss
 |     \
hit      v
 |    PostgreSQL
 |        |
 |        v
 |    Redis SET
 |        |
 └────────┘
      |
      v
   Response
```

Redis is used as a cache in front of PostgreSQL.

---

# 4. Cache-Aside Pattern

The application uses the cache-aside pattern.

Conceptually:

```python
def get_url(short_code):
    cached = redis.get(f"url:{short_code}")

    if cached is not None:
        return cached

    url = database.query(short_code)

    redis.setex(
        f"url:{short_code}",
        300,
        url,
    )

    return url
```

The application explicitly decides when to read from and write to the cache.

---

## Cache Hit

A cache hit occurs when Redis already contains the requested value.

```text
Client
   |
   v
FastAPI
   |
   v
Redis
   |
  HIT
   |
   v
Response
```

PostgreSQL is not queried.

---

## Cache Miss

A cache miss occurs when Redis does not contain the requested value.

```text
Client
   |
   v
FastAPI
   |
   v
Redis
   |
  MISS
   |
   v
PostgreSQL
   |
   v
Redis SET
   |
   v
Response
```

The database is queried and the result is placed in Redis for future requests.

---

# 5. Cache Hit Ratio

The cache hit ratio is:

```text
cache hits
------------------------
total cache lookups
```

For example:

```text
10,000 total requests
9,000 cache hits
1,000 cache misses
```

Then:

```text
hit ratio = 9000 / 10000 = 0.90 = 90%
```

If incoming traffic is:

```text
5,000 RPS
```

and the cache hit ratio is:

```text
90%
```

then approximately:

```text
5000 × (1 - 0.90) = 500
```

requests per second reach PostgreSQL.

Therefore:

```text
Incoming traffic:  5,000 RPS
Redis hits:        4,500 RPS
PostgreSQL load:     500 RPS
```

A high cache hit ratio can dramatically reduce database load.

---

# 6. Experiment 1 — No Cache vs Redis

Run the same read workload with Redis disabled and enabled.

Recommended concurrency levels:

```text
100 users
250 users
500 users
```

Record:

| Users | Cache | RPS | p50 | p95 | p99 | DB CPU | Hit Ratio |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | No |  |  |  |  |  | N/A |
| 250 | No |  |  |  |  |  | N/A |
| 500 | No |  |  |  |  |  | N/A |
| 100 | Yes |  |  |  |  |  |  |
| 250 | Yes |  |  |  |  |  |  |
| 500 | Yes |  |  |  |  |  |  |

## Questions

1. Does Redis increase throughput?
2. Does Redis reduce p95 or p99 latency?
3. How much does PostgreSQL CPU usage decrease?
4. At what cache hit ratio does Redis become particularly useful?
5. Is Redis itself becoming a bottleneck?

---

# 7. Experiment 2 — Different Access Patterns

The usefulness of caching depends strongly on the request distribution.

## Case A — Low Reuse

Generate requests for many different URLs:

```text
abc001
abc942
abc513
abc188
...
```

Expected behavior:

```text
many unique keys
    |
    v
many cache misses
    |
    v
low hit ratio
    |
    v
PostgreSQL still receives substantial traffic
```

Record:

```text
Hit ratio: ______ %
RPS:       ______
p95:       ______
DB CPU:    ______
```

---

## Case B — High Reuse

Generate most requests against a small group of popular URLs:

```text
google
youtube
openai
github
```

Expected behavior:

```text
repeated hot keys
    |
    v
high cache hit ratio
    |
    v
few DB queries
    |
    v
lower database load
```

Record:

```text
Hit ratio: ______ %
RPS:       ______
p95:       ______
DB CPU:    ______
```

## Observation

The usefulness of caching depends on the access pattern, not only on total traffic volume.

---

# 8. TTL

A cached value should not necessarily remain forever.

For example:

```python
redis.setex(
    f"url:{short_code}",
    300,
    long_url,
)
```

sets:

```text
TTL = 300 seconds
```

After five minutes the cached entry expires.

The next request causes:

```text
cache miss
    |
    v
database lookup
    |
    v
cache repopulation
```

---

## TTL Tradeoff

### Long TTL

Advantages:

```text
higher hit ratio
fewer DB queries
lower read latency
```

Disadvantages:

```text
data may remain stale longer
changes propagate more slowly
```

### Short TTL

Advantages:

```text
fresher data
less stale-cache risk
```

Disadvantages:

```text
more cache misses
more PostgreSQL traffic
lower hit ratio
```

There is no universally correct TTL.

The correct choice depends on:

- How frequently the data changes
- How harmful stale data is
- How expensive database reads are
- Expected traffic
- Available cache memory

---

# 9. Experiment 3 — Cache Consistency

Suppose Redis contains:

```text
abc123 → https://google.com
```

Then PostgreSQL is updated to:

```text
abc123 → https://openai.com
```

but Redis is not changed.

A new request:

```text
GET /urls/abc123
```

may still return:

```text
https://google.com
```

This is a stale-cache problem.

The two systems disagree:

```text
PostgreSQL → openai.com
Redis      → google.com
```

---

# 10. Cache Invalidation

One common update strategy is:

```text
1. Update PostgreSQL
2. Delete the corresponding cache entry
```

For example:

```python
update_database(short_code, new_url)

redis.delete(f"url:{short_code}")
```

The next read becomes:

```text
Redis MISS
    |
    v
PostgreSQL
    |
    v
new value
    |
    v
Redis SET
```

This avoids keeping the old cached value after a successful database update.

---

# 11. Experiment 4 — Redis Failure

Run Locust while Redis is active.

Then stop Redis:

```bash
docker compose stop redis
```

Observe:

- Does the API fail immediately?
- Does it fall back to PostgreSQL?
- Does latency increase?
- Does PostgreSQL CPU usage increase?
- Do requests time out?
- Does the API recover when Redis restarts?

Restart Redis:

```bash
docker compose start redis
```

Record:

```text
Behavior before Redis failure:
________________________________

Behavior during Redis failure:
________________________________

Behavior after Redis restart:
________________________________
```

---

# 12. Graceful Degradation

For this URL-shortener system, Redis should ideally be an optimization rather than a strict dependency.

Desired behavior:

```text
Redis available
      |
      v
FastAPI → Redis
```

If Redis fails:

```text
Redis unavailable
      |
      v
FastAPI → PostgreSQL
```

The service may become slower, but it should still function.

This is graceful degradation.

---

# 13. Cascading Failure

Graceful fallback does not automatically mean the system is safe.

Suppose:

```text
Incoming traffic:        5,000 RPS
Cache hit ratio:             95%
PostgreSQL capacity:       1,000 RPS
```

Normally PostgreSQL receives:

```text
5000 × (1 - 0.95)
= 250 RPS
```

This is safe.

If Redis fails, PostgreSQL may suddenly receive:

```text
5,000 RPS
```

which exceeds its capacity.

The resulting chain may look like:

```text
Redis fails
    |
    v
all reads fall through
    |
    v
PostgreSQL overloaded
    |
    v
database latency rises
    |
    v
connection pool fills
    |
    v
API latency rises
    |
    v
requests fail
```

This is an example of cascading failure.

---

# 14. Experiment 5 — Cache Stampede

Clear Redis:

```bash
redis-cli FLUSHALL
```

Then generate many concurrent requests for the same key:

```text
GET /urls/google
GET /urls/google
GET /urls/google
GET /urls/google
...
```

Suppose 500 requests arrive at nearly the same time.

All may perform:

```text
Redis GET
    |
   MISS
```

and then all issue the same PostgreSQL query.

Conceptually:

```text
500 requests
      |
      v
500 cache misses
      |
      v
500 DB queries
```

although only one database lookup was logically necessary.

This is called:

```text
cache stampede
```

or:

```text
thundering herd
```

Record:

```text
Number of concurrent users: ______
DB query rate before FLUSHALL: ______
DB query rate after FLUSHALL:  ______
p95 before: ______
p95 after:  ______
```

---

# 15. Possible Cache-Stampede Mitigation

One approach is request coalescing or locking:

```text
500 requests
      |
      v
Redis MISS
      |
      v
one request obtains lock
      |
      v
one DB query
      |
      v
populate Redis
      |
      v
remaining requests use cached value
```

A production implementation must also think about:

- Lock expiration
- Deadlocks
- Request timeouts
- Failed cache rebuilds
- Multiple application instances

This week, understanding the problem is more important than implementing a sophisticated distributed lock.

---

# 16. Interview Exercise

Consider:

```text
Traffic:                20,000 RPS
Redis hit ratio:            95%
PostgreSQL capacity:      2,000 QPS
Redis latency:               2 ms
Database latency:           40 ms
```

## Question 1

How many queries reach PostgreSQL?

```text
20,000 × (1 - 0.95)
= 1,000 QPS
```

Therefore:

```text
PostgreSQL load ≈ 1,000 QPS
```

which is below its stated 2,000-QPS capacity.

---

## Question 2

What happens if Redis fails?

Without the cache, PostgreSQL could receive:

```text
20,000 QPS
```

while its capacity is only:

```text
2,000 QPS
```

Therefore a naive database fallback could overload PostgreSQL.

Potential protections include:

- Rate limiting
- Load shedding
- Timeouts
- Circuit breakers
- Local caching
- Database read replicas
- Request prioritization

---

## Question 3

Should every URL be cached?

Not necessarily.

Suppose the system stores:

```text
1 billion URLs
```

but most requests are concentrated on:

```text
10 million popular URLs
```

Caching the entire dataset would waste memory.

It is often better to allow frequently accessed data to become hot naturally.

---

# 17. Key Lessons

## 1. Redis is primarily useful when requests have reuse

A cache cannot eliminate database work if almost every request asks for different data.

---

## 2. Cache hit ratio matters

A 95% hit ratio can reduce database traffic by approximately 95%.

---

## 3. Caching introduces state duplication

Once data exists in both PostgreSQL and Redis, consistency becomes a problem.

---

## 4. TTL is a tradeoff

Long TTL:

```text
better performance
more stale-data risk
```

Short TTL:

```text
fresher data
more database traffic
```

---

## 5. A cache can create new failure modes

Redis failure can push a sudden surge of traffic toward PostgreSQL.

---

## 6. Cache misses can synchronize

Many simultaneous misses for one hot key may generate a cache stampede.

---

## 7. A cache should solve a measured problem

Do not add Redis simply because Redis is common in system-design diagrams.

The reasoning should be:

```text
measure database load
        |
        v
identify repeated expensive reads
        |
        v
introduce cache
        |
        v
measure hit ratio and latency
        |
        v
test failure behavior
```

---

# 18. Week 3 Conclusions

This week's experiments introduce Redis as a read cache in front of PostgreSQL.

The main performance benefit comes from serving repeated reads without querying the database.

However, Redis introduces new concerns:

- Cache invalidation
- Stale data
- TTL selection
- Memory usage
- Cache failure
- Cascading database overload
- Cache stampede

The most important lesson is:

> A cache trades database load and latency for additional state, consistency problems, and failure modes.

The next architectural step is to scale the application tier itself:

```text
                  ┌→ FastAPI 1
Client → LB ──────┤
                  └→ FastAPI 2
                        |
                  Redis/PostgreSQL
```

Week 4 will focus on:

- Horizontal scaling
- Load balancing
- Stateless services
- Session state
- Failure of individual application instances
