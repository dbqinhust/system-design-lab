# Week 02 — PostgreSQL, Indexes, and Connection Pools

## Goal

Understand how a database becomes a system bottleneck and how to diagnose it before scaling the wrong component.

Architecture:

```text
Client / Locust
      |
      v
   FastAPI
      |
      v
 PostgreSQL
```

---

## 1. Core Ideas

### Database bottleneck
If API CPU is low but PostgreSQL CPU, I/O, query latency, or connection usage is high, the database is probably limiting throughput.

**Key lesson:** Scaling FastAPI does not help if PostgreSQL is the bottleneck.

---

### Indexes

Without an index:

```sql
SELECT long_url
FROM urls
WHERE short_code = 'abc123';
```

PostgreSQL may perform a:

```text
Seq Scan
```

With an index:

```sql
CREATE UNIQUE INDEX idx_urls_short_code
ON urls(short_code);
```

PostgreSQL can use an:

```text
Index Scan
```

Use:

```sql
EXPLAIN ANALYZE
SELECT long_url
FROM urls
WHERE short_code = 'abc123';
```

to verify the query plan.

**Trade-off:**

```text
More useful indexes
      |
      +--> faster reads
      |
      +--> more storage
      +--> more expensive INSERT / UPDATE / DELETE
```

Do not index every column. Index according to real query patterns.

---

## 2. Connection Pools

A connection pool limits how many database connections the application can use concurrently.

Example:

```text
250 requests
     |
     v
FastAPI
     |
     v
DB connection pool
[C1 C2 C3 C4 C5]
     |
     v
PostgreSQL
```

If all five connections are busy, other requests wait.

Approximate response time:

```text
response time
=
connection wait
+
database query time
+
application time
```

Increasing the pool can help until PostgreSQL itself becomes saturated.

Example pattern:

| Pool Size | RPS | p95 |
|---:|---:|---:|
| 5 | 500 | 180 ms |
| 10 | 750 | 140 ms |
| 20 | 900 | 170 ms |
| 50 | 880 | 420 ms |

**Lesson:** More connections do not mean unlimited throughput.

---

## 3. Useful Capacity Intuition

If each active connection executes one query at a time:

```text
DB throughput ≈ active connections / average query time
```

Example:

```text
20 connections
100 ms/query = 0.1 s/query

20 / 0.1 ≈ 200 queries/s
```

This is only an approximation because real systems also have contention, CPU, I/O, locks, and other overhead.

---

## 4. What to Measure

During load tests, record:

- RPS
- p50 / p95 / p99 latency
- API CPU
- PostgreSQL CPU
- DB connection usage
- query latency
- connection-pool wait time
- failure rate

A useful symptom:

```text
API CPU       = 25%
Postgres CPU  = 95%
DB connections = 200/200
p95           = 1.2 s
```

Likely conclusion:

> The database is a stronger bottleneck candidate than the API servers.

---

## 5. Failure Experiments

### PostgreSQL unavailable

Stop PostgreSQL while traffic is running:

```bash
docker compose stop postgres
```

Observe:

- Does the API fail immediately or hang?
- What status code is returned?
- How long does failure detection take?
- Does the connection pool recover?
- Does the API recover after PostgreSQL restarts?

Restart:

```bash
docker compose start postgres
```

---

### Slow queries

Use:

```sql
SELECT pg_sleep(1);
```

With 5 connections and ~1 second/query:

```text
maximum ≈ 5 queries/s
```

Extra requests wait for a connection.

This demonstrates that low throughput can result from a dependency even when FastAPI itself has plenty of CPU.

---

## 6. Interview Reasoning

Suppose:

```text
10 FastAPI instances
        |
        v
   PostgreSQL

Traffic          = 5,000 RPS
API CPU          = 25%
Postgres CPU     = 95%
DB connections   = 200/200
p95              = 1.2 s
```

### Should we add more FastAPI instances?

Probably not first. The API tier has spare capacity while PostgreSQL appears saturated.

### Should we increase DB connections from 200 to 500?

Not automatically. More connections can increase contention and make an overloaded database slower.

First investigate:

- slow queries
- missing indexes
- query volume
- connection wait time
- locks
- CPU
- disk/I/O

### One query causes most of the load and lacks an index?

Add the appropriate index, then measure again before introducing Redis, replicas, or sharding.

---

## 7. Week 2 Mental Model

```text
Symptom
  |
  v
Measure each component
  |
  v
Find the saturated resource
  |
  v
Improve that bottleneck
  |
  v
Load-test again
```

### Most important takeaway

> **A system is limited by its current bottleneck. Scaling another layer does not remove that bottleneck.**

### Remember

```text
Week 1:
More concurrency eventually creates queueing.

Week 2:
Find which component is creating that queueing.

Week 3:
Reduce database work with caching.
```
