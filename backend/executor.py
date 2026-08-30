"""
Action executor — the final stage of the pipeline. Reads every classified,
reasoned event that hasn't been executed yet, and carries out its bounded
action. Real Razorpay payment IDs get a real API call (fetch/verify state).
Simulated payment IDs get a logged, simulated execution — Razorpay has no
API to retroactively retry a specific past payment, so "real execution"
here means confirming live payment state via the API.

Guards against double-execution via the executed_at column: any row with
executed_at already set is skipped.
"""

import os
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# Real Razorpay payment IDs always start with "pay_" followed by a real
# Razorpay-generated string. Our simulated ones use the "pay_sim_" prefix
# deliberately so we can tell them apart without a separate DB flag.
def is_real_payment(payment_id):
    return not payment_id.startswith("pay_sim_")


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return create_client(url, key)


def verify_real_payment(payment_id):
    """Real API call: fetch current state from Razorpay to confirm before acting."""
    url = f"https://api.razorpay.com/v1/payments/{payment_id}"
    response = requests.get(url, auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if response.status_code == 200:
        data = response.json()
        return True, f"Verified via Razorpay API: status={data['status']}, captured={data['captured']}"
    return False, f"Razorpay API call failed: {response.status_code} {response.text}"


def execute_action(event):
    """
    Executes one event's bounded action. Returns a short execution note
    describing what actually happened (for the audit log).
    """
    action = event["action_taken"]
    payment_id = event["payment_id"]

    if is_real_payment(payment_id):
        success, detail = verify_real_payment(payment_id)
        prefix = "[REAL API]"
        return f"{prefix} action={action} | {detail}"

    # Simulated payment — no real API call possible, log the intended action
    action_descriptions = {
        "auto_retry": "Simulated: would trigger a fresh checkout retry for the customer.",
        "wait_and_reassure": "Simulated: no retry triggered. Would send customer a wait/reassurance notification and continue polling.",
        "notify_customer_action_required": "Simulated: would notify customer their action is needed (update card/funds/etc).",
        "capture_and_notify": "Simulated: payment already captured, would send success confirmation to customer.",
        "no_action": "Simulated: customer cancelled, no further action taken.",
        "escalate_to_merchant": "Simulated: would flag this payment in the merchant dashboard for manual review.",
    }
    detail = action_descriptions.get(action, f"Simulated: unrecognized action '{action}', no handler defined.")
    return f"[SIMULATED] action={action} | {detail}"


def run_executor(dry_run=False):
    supabase = get_supabase_client()

    response = (
        supabase.table("payment_events")
        .select("*")
        .not_.is_("action_taken", "null")
        .is_("executed_at", "null")
        .execute()
    )
    events = response.data
    print(f"Found {len(events)} events ready to execute")

    executed_count = 0
    for event in events:
        execution_note = execute_action(event)
        print(f"  {event['payment_id']}: {execution_note}")

        if not dry_run:
            supabase.table("payment_events").update({
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("payment_id", event["payment_id"]).execute()
            executed_count += 1

    if dry_run:
        print(f"\n(dry run — {len(events)} events would be executed, nothing written)")
    else:
        print(f"\nExecuted and stamped {executed_count} events")

    return executed_count


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    run_executor(dry_run=dry_run)