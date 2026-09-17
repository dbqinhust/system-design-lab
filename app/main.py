import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.cache import cache_url, get_cached_url, invalidate_url
from app.database import get_session
from app.models import URL
from app.schemas import URLCreate, URLRead
import random
import time

app = FastAPI()

DatabaseSession = Annotated[Session, Depends(get_session)]


@app.post("/urls", response_model=URLRead, status_code=status.HTTP_201_CREATED)
def create_url(payload: URLCreate, session: DatabaseSession):
    url = URL(**payload.model_dump())
    session.add(url)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Short code already exists",
        ) from exc
    session.refresh(url)
    invalidate_url(url.short_code)
    return url


@app.get("/urls/{short_code}", response_model=URLRead)
def get_url(short_code: str, session: DatabaseSession):
    cached_url = get_cached_url(short_code)
    if cached_url is not None:
        return cached_url

    url = session.scalar(
        select(URL).where(URL.short_code == short_code).order_by(URL.id).limit(1)
    )
    if url is None:
        raise HTTPException(status_code=404, detail="URL not found")

    response = URLRead.model_validate(url)
    cache_url(response)
    return response


@app.get("/pool-test")
def pool_test(session: DatabaseSession):
    delay = float(os.getenv("DB_POOL_TEST_DELAY", "0.1"))
    session.execute(text("SELECT pg_sleep(:delay)"), {"delay": delay})
    return {"status": "ok", "delay_seconds": delay}


@app.get("/db-health")
def database_health(session: DatabaseSession):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "ok"}


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
