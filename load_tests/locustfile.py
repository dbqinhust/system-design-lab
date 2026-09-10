from locust import HttpUser, constant, task


class APIUser(HttpUser):
    wait_time = constant(0)

    @task
    def pool_test(self):
        self.client.get("/pool-test")
