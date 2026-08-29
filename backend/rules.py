"""
Rules layer — classifies payment events using deterministic logic based on
error_code. Handles every case except "ambiguous", which is left for the
LLM reasoning layer (see reasoning.py, not yet built).
"""

import os
from dotenv import load_dotenv
from supabase import create_client

from error_codes import ERROR_CODES

load_dotenv()

ACTION_MAP = {
    "success": "capture_and_notify",
    "safe_retry": "auto_retry",
    "late_auth": "wait_and_reassure",
    "no_retry": "notify_customer_action_required",
    "cancelled": "no_action",
    "escalate": "escalate_to_merchant",
    # "ambiguous" deliberately excluded — reasoning layer decides this
}

REASON_MAP = {
    "success": "Payment captured successfully, no error present.",
    "safe_retry": "Known technical error on gateway/bank side, safe to auto-retry.",
    "late_auth": "Payment timed out — Razorpay may still confirm with the bank up to 3 days later. Must not retry (double-charge risk).",
    "no_retry": "Customer-side issue (funds/card/auth) — retrying won't help, customer must act.",
    "cancelled": "Customer chose not to complete payment — no action needed.",
    "escalate": "Flagged as risky by bank — requires manual merchant review, not automation.",
}


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return create_client(url, key)


def classify_event(event):
    """
    Returns (classification, action_taken, reasoning) for a single event.
    action_taken and reasoning are None for 'ambiguous' cases.
    """
    error_code = event.get("error_code")

    if error_code is None:
        bucket = "success"
    else:
        error_info = ERROR_CODES.get(error_code)
        if error_info is None:
            # Unknown code we haven't classified — treat as ambiguous rather
            # than guessing, so it surfaces for review instead of silently
            # misclassifying.
            bucket = "ambiguous"
        else:
            bucket = error_info["bucket"]

    if bucket == "ambiguous":
        return bucket, None, None

    action = ACTION_MAP[bucket]
    reasoning = REASON_MAP[bucket]
    return bucket, action, reasoning


def run_rules_layer():
    supabase = get_supabase_client()

    # Pull all unclassified rows
    response = supabase.table("payment_events").select("*").is_("classification", "null").execute()
    events = response.data
    print(f"Found {len(events)} unclassified events")

    counts = {}
    for event in events:
        classification, action, reasoning = classify_event(event)
        counts[classification] = counts.get(classification, 0) + 1

        update_data = {"classification": classification}
        if action is not None:
            update_data["action_taken"] = action
            update_data["reasoning"] = reasoning
        # if classification == "ambiguous", leave action_taken/reasoning as-is (null)
        # for the reasoning layer to fill in later

        supabase.table("payment_events").update(update_data).eq("payment_id", event["payment_id"]).execute()

    print("Classification counts:", counts)
    return counts


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv

    supabase = get_supabase_client()
    response = supabase.table("payment_events").select("*").is_("classification", "null").execute()
    events = response.data
    print(f"Found {len(events)} unclassified events")

    counts = {}
    for event in events:
        classification, action, reasoning = classify_event(event)
        counts[classification] = counts.get(classification, 0) + 1

        if dry_run:
            print(f"{event['payment_id']} | error_code={event.get('error_code')} -> classification={classification}, action={action}")
        else:
            update_data = {"classification": classification}
            if action is not None:
                update_data["action_taken"] = action
                update_data["reasoning"] = reasoning
            supabase.table("payment_events").update(update_data).eq("payment_id", event["payment_id"]).execute()

    print("\nClassification counts:", counts)
    if dry_run:
        print("(dry run — nothing written to Supabase)")