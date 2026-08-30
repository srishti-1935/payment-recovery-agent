"""
Rules layer — classifies payment events using deterministic logic based on
error_code. Handles every case except "ambiguous", which is left for the
LLM reasoning layer (see reasoning.py). Also generates a customer-facing
message per action, kept separate from the internal audit-log reasoning.
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

CUSTOMER_MESSAGE_MAP = {
    "success": "Your payment was successful. Thank you!",
    "safe_retry": "We noticed a temporary issue with your payment. We're automatically retrying it now — no action needed from you.",
    "late_auth": "Your payment is still being confirmed by your bank. This can take a little time. Your money is safe — we'll update you as soon as it's confirmed. Please don't attempt to pay again.",
    "no_retry": "Your payment didn't go through. Please check your card details, available balance, or try a different payment method.",
    "cancelled": "It looks like you didn't complete this payment. Feel free to try again whenever you're ready.",
    "escalate": "We're reviewing this payment for your security. Our team will follow up with you shortly.",
}


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return create_client(url, key)


def classify_event(event):
    """
    Returns (classification, action_taken, reasoning, customer_message) for
    a single event. action_taken, reasoning, and customer_message are None
    for 'ambiguous' cases — those are decided by the reasoning layer.
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
        return bucket, None, None, None

    action = ACTION_MAP[bucket]
    reasoning = REASON_MAP[bucket]
    customer_message = CUSTOMER_MESSAGE_MAP[bucket]
    return bucket, action, reasoning, customer_message


def run_rules_layer():
    supabase = get_supabase_client()

    # Pull all unclassified rows
    response = supabase.table("payment_events").select("*").is_("classification", "null").execute()
    events = response.data
    print(f"Found {len(events)} unclassified events")

    counts = {}
    for event in events:
        classification, action, reasoning, customer_message = classify_event(event)
        counts[classification] = counts.get(classification, 0) + 1

        update_data = {"classification": classification}
        if action is not None:
            update_data["action_taken"] = action
            update_data["reasoning"] = reasoning
            update_data["customer_message"] = customer_message
        # if classification == "ambiguous", leave action_taken/reasoning/
        # customer_message as-is (null) for the reasoning layer to fill in

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
        classification, action, reasoning, customer_message = classify_event(event)
        counts[classification] = counts.get(classification, 0) + 1

        if dry_run:
            print(f"{event['payment_id']} | error_code={event.get('error_code')} -> classification={classification}, action={action}")
        else:
            update_data = {"classification": classification}
            if action is not None:
                update_data["action_taken"] = action
                update_data["reasoning"] = reasoning
                update_data["customer_message"] = customer_message
            supabase.table("payment_events").update(update_data).eq("payment_id", event["payment_id"]).execute()

    print("\nClassification counts:", counts)
    if dry_run:
        print("(dry run — nothing written to Supabase)")