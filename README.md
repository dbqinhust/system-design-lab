# System Design Lab

Hands-on system design learning through implementation,
load testing, failure testing, and architecture evolution.

## Run locally

With your virtual environment activated, run from the project root:

```bash
pip install -r requirements.txt
docker compose up -d postgres-sd
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

The table follows the original SQL: short codes are not unique. If duplicates
exist, GET returns the row with the lowest ID.

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
