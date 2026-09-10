"""Generate many URL rows for testing index usage.

Run as module from repository root:

    python -m app.generate_data --count 100000 --batch-size 5000 --unique-short-codes 100

This will create many rows where the same `short_code` can be associated with many `long_url` values.
"""
from __future__ import annotations

import argparse
import random
import string
import time
import uuid
from typing import List

from app.database import SessionLocal
from app.models import URL


def make_short_code_pool(n: int, length: int = 6) -> List[str]:
    chars = string.ascii_letters + string.digits
    return ["".join(random.choices(chars, k=length)) for _ in range(n)]


def make_long_url() -> str:
    return f"https://example.com/resource/{uuid.uuid4()}"


def generate_rows(count: int, batch_size: int, unique_short_codes: int, short_code_length: int) -> None:
    pool = make_short_code_pool(unique_short_codes, short_code_length)
    session = SessionLocal()
    inserted = 0
    start = time.time()
    try:
        while inserted < count:
            to_insert = min(batch_size, count - inserted)
            batch = []
            for _ in range(to_insert):
                batch.append({
                    "short_code": random.choice(pool),
                    "long_url": make_long_url(),
                })
                inserted += 1

            # Use bulk_insert_mappings for speed
            session.bulk_insert_mappings(URL, batch)
            session.commit()

            if inserted % max(1, count // 10) == 0 or inserted == count:
                elapsed = time.time() - start
                print(f"Inserted {inserted}/{count} rows ({elapsed:.1f}s)")

        total_time = time.time() - start
        print(f"Done. Inserted {inserted} rows in {total_time:.1f}s")
    finally:
        session.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate URL rows for testing")
    p.add_argument("--count", type=int, default=100000, help="Total rows to insert")
    p.add_argument("--batch-size", type=int, default=5000, help="Rows per DB batch commit")
    p.add_argument("--unique-short-codes", type=int, default=100, help="How many distinct short codes to reuse")
    p.add_argument("--short-code-length", type=int, default=6, help="Length of generated short codes")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print(
        f"Generating {args.count} rows with {args.unique_short_codes} short_codes (length={args.short_code_length}) in batches of {args.batch_size}"
    )
    generate_rows(args.count, args.batch_size, args.unique_short_codes, args.short_code_length)


if __name__ == "__main__":
    main()
