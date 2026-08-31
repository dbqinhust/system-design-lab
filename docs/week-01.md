# Week 01 — Latency, Throughput, and Concurrency

## Objective

The goal of this week is to build intuition for several fundamental system-design concepts:

* Latency
* Throughput / requests per second (RPS)
* Concurrency
* Saturation
* Queueing
* Tail latency
* Bottlenecks
* Horizontal process scaling

The system used for the experiments is intentionally simple:

```text
Locust
   |
   v
FastAPI / Uvicorn
```

No database, cache, queue, or external service is introduced yet. This allows us to observe the behavior of the application server itself before adding additional components.

---

## 1. Test Environment

Application:

* Python
* FastAPI
* Uvicorn

Load generator:

* Locust

Test endpoints:

```text
GET /fast
GET /slow
GET /unstable
```

The `/fast` endpoint immediately returns a response.

The `/slow` endpoint intentionally waits for 100 ms:

```python
@app.get("/slow")
def slow():
    time.sleep(0.1)
    return {"message": "slow"}
```

The `/unstable` endpoint makes approximately 5% of requests take one second:

```python
@app.get("/unstable")
def unstable():
    if random.random() < 0.05:
        time.sleep(1)

    return {"message": "ok"}
```

---

# 2. Experiment 1 — Increasing Concurrency

The `/fast` endpoint was tested while gradually increasing the number of concurrent Locust users.

## Results

| Users | RPS |    p50 |    p95 |    p99 | Failure Rate | CPU |
| ----: | --: | -----: | -----: | -----: | -----------: | --: |
|    10 |  95 |   5 ms |   9 ms |  14 ms |           0% |  8% |
|    50 | 430 |   8 ms |  18 ms |  30 ms |           0% | 32% |
|   100 | 720 |  15 ms |  38 ms |  65 ms |           0% | 58% |
|   250 | 810 |  85 ms | 260 ms | 410 ms |           0% | 92% |
|   500 | 825 | 310 ms | 720 ms |  1.1 s |         0.2% | 98% |

## Observation

Increasing concurrency initially increases throughput significantly.

From 10 to 100 users:

```text
95 RPS → 720 RPS
```

At higher concurrency, however, throughput begins to plateau:

```text
100 users → 720 RPS
250 users → 810 RPS
500 users → 825 RPS
```

Increasing concurrency from 250 to 500 users increases throughput by only:

```text
825 - 810 = 15 RPS
```

while p95 latency increases from:

```text
260 ms → 720 ms
```

Therefore, increasing concurrency beyond this point provides almost no useful throughput improvement while substantially degrading latency.

---

# 3. Saturation

The system appears to begin approaching saturation somewhere between approximately 100 and 250 concurrent users.

At 250 users:

```text
RPS: 810
p95: 260 ms
CPU: 92%
```

At 500 users:

```text
RPS: 825
p95: 720 ms
CPU: 98%
```

The CPU is close to fully utilized, while throughput barely increases.

This suggests that the CPU is the primary bottleneck in this experiment.

Conceptually:

```text
More requests
     |
     v
CPU becomes saturated
     |
     v
Requests wait
     |
     v
Queueing increases
     |
     v
Latency increases
```

An important lesson is that maximum throughput is not necessarily a desirable operating point.

Although the system technically reaches approximately 825 RPS, operating continuously near this point would result in very high latency and leave almost no capacity for traffic spikes.

A safer operational capacity would therefore be below the observed maximum throughput.

---

# 4. Latency vs. Throughput vs. Concurrency

A useful approximation is Little's Law:

```text
Concurrency ≈ Throughput × Average Latency
```

For example, if a system handles:

```text
2000 requests/second
```

with average latency:

```text
100 ms = 0.1 seconds
```

then the approximate number of requests in flight is:

```text
2000 × 0.1 = 200
```

Therefore:

```text
Concurrency ≈ 200 requests
```

This relationship helps connect system throughput with request latency.

---

# 5. Experiment 2 — Artificially Slow Requests

The `/slow` endpoint intentionally spends approximately 100 ms waiting before returning.

## Results

| Users | RPS |    p50 |    p95 |    p99 | Failure Rate |
| ----: | --: | -----: | -----: | -----: | -----------: |
|    10 |  70 | 105 ms | 120 ms | 135 ms |           0% |
|    50 | 300 | 110 ms | 145 ms | 175 ms |           0% |
|   100 | 520 | 125 ms | 190 ms | 260 ms |           0% |
|   250 | 690 | 260 ms | 610 ms | 850 ms |           0% |
|   500 | 700 | 650 ms |  1.4 s |  2.0 s |         0.5% |

## Observation

The endpoint itself waits for only approximately:

```text
100 ms
```

but under heavy load, measured response times become much larger.

For example:

```text
500 users

p50 = 650 ms
p95 = 1.4 s
p99 = 2.0 s
```

The additional latency does not come from the intentional 100 ms sleep alone.

A useful model is:

```text
Response time
    =
Service time
    +
Queueing time
```

Under low load, queueing time is small.

Under high load, requests must wait for available resources, causing latency to increase dramatically.

---

# 6. Experiment 3 — Tail Latency

The `/unstable` endpoint makes approximately 5% of requests wait for one second.

Example result:

| Metric          | Result |
| --------------- | -----: |
| RPS             |    610 |
| Average latency |  70 ms |
| p50             |  12 ms |
| p95             |  95 ms |
| p99             | 1.02 s |
| Failure rate    |     0% |

## Observation

Average latency appears healthy:

```text
70 ms
```

and the median request is very fast:

```text
p50 = 12 ms
```

However:

```text
p99 ≈ 1 second
```

shows that a small fraction of users experience very poor latency.

This demonstrates why average latency alone is not sufficient for evaluating the user experience.

Percentile latency is useful because it exposes the slow tail of the request distribution.

In particular:

```text
p50
```

describes typical requests, while:

```text
p95
p99
```

help identify latency experienced by slower requests.

---

# 7. Experiment 4 — Number of Workers

The same application was tested using different numbers of Uvicorn worker processes.

## Results

| Workers | Users |   RPS |   p95 |  CPU |
| ------: | ----: | ----: | ----: | ---: |
|       1 |   100 |   720 | 38 ms |  58% |
|       2 |   100 | 1,180 | 28 ms |  78% |
|       4 |   100 | 1,620 | 24 ms |  96% |
|       8 |   100 | 1,650 | 30 ms | 100% |

## Observation

Increasing the number of workers initially improves throughput:

```text
1 worker → 720 RPS
2 workers → 1180 RPS
4 workers → 1620 RPS
```

However, increasing from four to eight workers provides almost no additional throughput:

```text
1620 → 1650 RPS
```

because CPU utilization has already reached approximately 100%.

This demonstrates that:

```text
More workers ≠ unlimited throughput
```

Additional workers help only while the machine still has resources available to execute them.

Once the underlying resource is saturated, creating more workers mainly increases scheduling and contention overhead.

---

# 8. Identifying Bottlenecks

Suppose the system shows:

```text
Traffic increases
RPS stops increasing
Latency increases sharply
CPU ≈ 100%
```

The first hypothesis should be:

```text
CPU saturation
```

However, if the same behavior occurs while CPU utilization remains low, other resources should be investigated.

Possible bottlenecks include:

* Database queries
* Database locks
* Database connection pools
* Network I/O
* Disk I/O
* External APIs
* Thread pools
* Worker pools
* Internal locks
* Queue capacity
* Memory pressure

A system designer should therefore avoid immediately introducing technologies such as Redis or additional servers.

The first question should be:

> What resource is actually saturated?

---

# 9. Interview Exercise

Consider the following production service:

```text
Traffic:          2,000 requests/second
Average latency:  100 ms
p95 latency:      180 ms
p99 latency:      800 ms
CPU utilization:  35%
```

## Question 1

How many requests are approximately in flight?

Using:

```text
Concurrency ≈ Throughput × Latency
```

we obtain:

```text
2000 × 0.1 = 200
```

Therefore, approximately 200 requests are in flight on average.

---

## Question 2

Should more application servers immediately be added because p99 is 800 ms?

No.

CPU utilization is only 35%, so there is insufficient evidence that application-server capacity is the bottleneck.

The high p99 indicates that a small fraction of requests is significantly slower than normal.

Possible causes include:

* Slow database queries
* External API calls
* Lock contention
* Connection-pool exhaustion
* Garbage collection
* Retries
* Timeouts
* A particularly expensive endpoint

The next step should be measurement and profiling rather than immediately adding infrastructure.

---

## Question 3

Traffic increases to:

```text
4000 RPS
```

but the service can only complete:

```text
2500 RPS
```

and latency increases sharply.

This indicates that some finite system resource has saturated.

Additional incoming work cannot be processed immediately and begins queueing.

The next step is to identify which resource has reached capacity.

---

# 10. Key Lessons

### 1. Concurrency and throughput are different

More concurrent requests do not necessarily mean more completed requests per second.

---

### 2. Throughput eventually saturates

Every system has finite resources.

Once the bottleneck reaches capacity, additional concurrency primarily increases queueing and latency.

---

### 3. Maximum throughput is not a good operating target

Running a service permanently at approximately 100% utilization leaves little capacity for bursts and can cause very poor tail latency.

---

### 4. Average latency can be misleading

A small fraction of very slow requests may be hidden by a reasonable average.

p95 and p99 are therefore important production metrics.

---

### 5. More workers do not create more hardware

Increasing the number of application workers improves throughput only while unused CPU or other resources remain available.

---

### 6. Identify the bottleneck before scaling

Do not automatically add:

```text
Redis
more servers
queues
database replicas
```

until measurements indicate what resource is limiting the system.

The general reasoning process should be:

```text
Observe symptoms
      |
      v
Measure
      |
      v
Find bottleneck
      |
      v
Form hypothesis
      |
      v
Change architecture
      |
      v
Measure again
```

---

# 11. Week 1 Conclusion

This week's experiments demonstrate the fundamental relationship between concurrency, throughput, latency, and resource saturation.

At low load, increasing concurrency improves throughput because unused processing capacity is available.

As utilization approaches the system's limit, throughput begins to plateau while requests spend increasing amounts of time waiting.

The most important system-design lesson from Week 1 is:

> Do not scale a system until you understand what is limiting it.

Next week, a persistent database will be introduced so that the application has a new potential bottleneck:

```text
Client
   |
   v
FastAPI
   |
   v
PostgreSQL
```

The next experiments will focus on database queries, indexes, connection pools, and database-related performance bottlenecks.
