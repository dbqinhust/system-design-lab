# System Design Lab

Hands-on system design learning through implementation,
load testing, failure testing, and architecture evolution.

## Run locally

With your virtual environment activated, run from the project root:

```bash
pip install -r requirements.txt
docker compose up -d postgres-sd redis
python -m app.init_db
uvicorn app.main:app --reload
```

Wait for PostgreSQL to accept connections before running the setup script.
The script creates `database_connection` and its `urls` table if missing;
it can be rerun, but does not migrate existing tables.
The default connection matches `docker-compose.yml`. Set `DATABASE_URL` to
override it (use a `postgresql+psycopg://` connection URL).

## URL endpoints

Create a URL (returns JSON with status 201):

```bash
curl -X POST http://localhost:8000/urls \
  -H 'Content-Type: application/json' \
  -d '{"short_code":"example","long_url":"https://example.com"}'
```

Retrieve the stored URL as JSON (returns 404 when absent):

```bash
curl http://localhost:8000/urls/example
```

`GET /urls/{short_code}` first checks Redis. On a cache miss it reads from
PostgreSQL and caches the response for `REDIS_URL_TTL_SECONDS` (five minutes by
default). If Redis is unavailable, the endpoint continues using PostgreSQL.
Creating a URL invalidates any cached entry for that short code.

## Redis cache load test

Use the same URL, Locust settings, Uvicorn worker count, and pool settings for
both runs. First disable Redis in `.env`:

```dotenv
REDIS_CACHE_ENABLED=false
```

Restart Uvicorn, then run the PostgreSQL baseline:

```bash
LOCUST_SHORT_CODE=00000917378f4a47 locust \
  -f load_tests/redis_cache.py --host http://localhost:8000 \
  --headless --users 50 --spawn-rate 10 --run-time 60s \
  --reset-stats --csv redis-off
```

Enable caching and restart Uvicorn again:

```dotenv
REDIS_CACHE_ENABLED=true
```

Warm the key and reset Redis's counters before running the same workload:

```bash
curl http://localhost:8000/urls/00000917378f4a47
docker compose exec redis redis-cli CONFIG RESETSTAT
LOCUST_SHORT_CODE=00000917378f4a47 locust \
  -f load_tests/redis_cache.py --host http://localhost:8000 \
  --headless --users 50 --spawn-rate 10 --run-time 60s \
  --reset-stats --csv redis-on
```

Compare RPS, median, p95, p99, and failures in `redis-off_stats.csv` and
`redis-on_stats.csv`. Confirm that the cached run reached Redis with:

```bash
docker compose exec redis redis-cli INFO stats | \
  grep -E 'keyspace_hits|keyspace_misses'
```

The warmed run should show almost all hits. Cache-on should reduce PostgreSQL
transactions, lower endpoint latency, and usually increase throughput.

Short codes are unique. Creating a URL with an existing short code returns
HTTP 409 Conflict.

For a database created before the unique constraint was added, run:

```bash
python -m app.migrate_unique_short_codes
```

The migration reports duplicate short codes and stops without deleting data.
If the generated rows are disposable, clear them and rerun the migration:

```sql
TRUNCATE TABLE database_connection.urls RESTART IDENTITY;
```

## Database outage test

Run the API with one worker:

```bash
uvicorn app.main:app --workers 1
```

In another terminal, start a steady 10 RPS workload and save the results:

```bash
locust -f load_tests/database_outage.py \
  --host http://localhost:8000 \
  --headless --users 30 --spawn-rate 10 --run-time 90s \
  --exit-code-on-error 0 \
  --csv database-outage
```

While Locust is running, stop PostgreSQL, wait about 20 seconds, and start it
again:

```bash
docker compose stop postgres-sd
docker compose start postgres-sd
```

`/db-health` returns 200 while PostgreSQL is reachable and a controlled 503
while it is unavailable. `DB_CONNECT_TIMEOUT` and Locust's request timeout keep
the test responsive during the outage. Review the terminal summary and the
generated `database-outage_stats.csv` and `database-outage_failures.csv` files.
The outage intentionally produces 503 failures. `--exit-code-on-error 0` keeps
Locust's final process status successful while still reporting those failures.
