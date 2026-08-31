from fastapi import FastAPI
import random
import time

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/fast")
def fast():
    return {"message": "fast"}


@app.get("/slow")
def slow():
    time.sleep(0.1)
    return {"message": "slow"}


@app.get("/very-slow")
def very_slow():
    time.sleep(0.5)
    return {"message": "very slow"}


@app.get("/unstable")
def unstable():
    if random.random() < 0.05:
        time.sleep(1)

    return {"message": "ok"}