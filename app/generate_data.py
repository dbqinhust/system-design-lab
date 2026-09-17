"""Generate many URL rows for testing index usage.

Run as module from repository root:

    python -m app.generate_data --count 100000 --batch-size 5000

Each generated row has a unique 16-character `short_code`.
"""
from __future__ import annotations

import argparse
import time
import uuid

from app.database import SessionLocal
from app.models import URL


def make_short_code(length: int = 16) -> str:
    return uuid.uuid4().hex[:length]


def make_long_url() -> str:
    return f"https://example.com/resource/{uuid.uuid4()}"


def generate_rows(count: int, batch_size: int, short_code_length: int) -> None:
    if not 1 <= short_code_length <= 16:
        raise ValueError("short-code-length must be between 1 and 16")
    if count > 16**short_code_length:
        raise ValueError("count exceeds the available short-code combinations")

    session = SessionLocal()
    generated_codes: set[str] = set()
    inserted = 0
    start = time.time()
    try:
        while inserted < count:
            to_insert = min(batch_size, count - inserted)
            batch = []
            for _ in range(to_insert):
                short_code = make_short_code(short_code_length)
                while short_code in generated_codes:
                    short_code = make_short_code(short_code_length)
                generated_codes.add(short_code)
                batch.append({
                    "short_code": short_code,
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
    p.add_argument("--short-code-length", type=int, default=16, help="Length of generated short codes")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print(
        f"Generating {args.count} rows with unique short codes "
        f"(length={args.short_code_length}) in batches of {args.batch_size}"
    )
    generate_rows(args.count, args.batch_size, args.short_code_length)


if __name__ == "__main__":
    main()
