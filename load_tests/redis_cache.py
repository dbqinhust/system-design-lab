"""Compare URL reads with the application cache enabled and disabled."""

import os

from locust import HttpUser, constant, task


SHORT_CODE = os.getenv("LOCUST_SHORT_CODE", "00000917378f4a47")


class URLReadUser(HttpUser):
    wait_time = constant(0)

    @task
    def get_url(self):
        self.client.get(
            f"/urls/{SHORT_CODE}",
            name="/urls/[short_code]",
            timeout=5,
        )
