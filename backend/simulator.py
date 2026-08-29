"""
Generates a simulated batch of Razorpay-style payment events for testing
the classification and reasoning pipeline. Uses real error codes/schema
discovered during live API exploration (see error_codes.py).
"""

import os
import random
import string
from datetime import datetime, timedelta

from dotenv import load_dotenv
from supabase import create_client

from error_codes import ERROR_CODES, BUCKET_CODES

load_dotenv()

# How many events per bucket (totals 80)
BUCKET_COUNTS = {
    "success": 30,
    "safe_retry": 10,
    "late_auth": 8,
    "no_retry": 15,
    "cancelled": 5,
    "escalate": 3,
    "ambiguous": 9,
}

REPEAT_CUSTOMER_IDS = [f"cust_rep_{i:02d}" for i in range(1, 6)]  # 5 fixed repeat customers


def _random_id(prefix, length=8):
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}_{suffix}"


def _random_amount():
    # ₹100.00 to ₹5000.00, in paise
    return random.randint(10000, 500000)


def _random_created_at():
    # skew recent: within last 3 days, weighted toward last 24h
    hours_ago = random.choices(
        [random.uniform(0, 24), random.uniform(24, 72)],
        weights=[0.6, 0.4],
    )[0]
    return (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat() + "Z"


def _make_event(bucket, running_id):
    payment_id = f"pay_sim_{running_id:04d}"
    customer_id = _random_id("cust")
    amount = _random_amount()
    created_at = _random_created_at()

    if bucket == "success":
        return {
            "payment_id": payment_id,
            "amount": amount,
            "status": "captured",
            "error_code": None,
            "error_description": None,
            "error_reason": None,
            "customer_id": customer_id,
            "retry_count": 0,
            "created_at": created_at,
            "classification": None,
            "action_taken": None,
            "reasoning": None,
        }

    error_code = random.choice(BUCKET_CODES[bucket])
    error_info = ERROR_CODES[error_code]
    status = "created" if bucket == "late_auth" else "failed"
    retry_count = random.choice([0, 0, 0, 1, 2]) if bucket in ("no_retry", "ambiguous") else 0

    return {
        "payment_id": payment_id,
        "amount": amount,
        "status": status,
        "error_code": error_code,
        "error_description": error_info["description"],
        "error_reason": error_info["reason"],
        "customer_id": customer_id,
        "retry_count": retry_count,
        "created_at": created_at,
        "classification": None,
        "action_taken": None,
        "reasoning": None,
    }


def generate_batch():
    events = []
    running_id = 1

    for bucket, count in BUCKET_COUNTS.items():
        for _ in range(count):
            events.append(_make_event(bucket, running_id))
            running_id += 1

    # Inject repeat-customer edge cases: pick ~10 non-success events,
    # overwrite their customer_id so a handful of customers show up
    # 2-3 times each (some same error, some different) — this is what
    # the reasoning layer will use "has this customer seen this before" on
    non_success = [e for e in events if e["status"] != "captured"]
    repeat_targets = random.sample(non_success, min(10, len(non_success)))
    for i, event in enumerate(repeat_targets):
        event["customer_id"] = REPEAT_CUSTOMER_IDS[i % len(REPEAT_CUSTOMER_IDS)]

    random.shuffle(events)
    return events


def insert_batch_to_supabase(events):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    supabase = create_client(url, key)

    result = supabase.table("payment_events").insert(events).execute()
    print(f"Inserted {len(result.data)} rows into Supabase")
    return result


if __name__ == "__main__":
    batch = generate_batch()
    print(f"Generated {len(batch)} events")

    # Sanity checks
    statuses = {}
    for e in batch:
        statuses[e["status"]] = statuses.get(e["status"], 0) + 1
    print("By status:", statuses)

    repeat_counts = {}
    for e in batch:
        if e["customer_id"] in REPEAT_CUSTOMER_IDS:
            repeat_counts[e["customer_id"]] = repeat_counts.get(e["customer_id"], 0) + 1
    print("Repeat customer counts:", repeat_counts)

    print("\nSample event:")
    print(batch[0])

    confirm = input(f"\nInsert these {len(batch)} events into Supabase? (y/n): ")
    if confirm.lower() == "y":
        insert_batch_to_supabase(batch)