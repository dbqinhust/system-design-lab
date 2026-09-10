"""Steady database health traffic for outage and recovery experiments."""

from locust import HttpUser, constant_pacing, task


class DatabaseUser(HttpUser):
    # With 30 users, this produces about 10 RPS while requests finish within 3s.
    wait_time = constant_pacing(3.0)

    @task
    def database_health(self):
        # Bound client-side waiting so an outage cannot stall a user indefinitely.
        self.client.get("/db-health", name="/db-health", timeout=3)
