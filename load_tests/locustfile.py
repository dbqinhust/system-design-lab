from locust import HttpUser, task, between


class APIUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def fast_endpoint(self):
        self.client.get("/unstable")
        