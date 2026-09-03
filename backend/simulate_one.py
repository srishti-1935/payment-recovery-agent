"""
Generates ONE new payment event and runs it through the full pipeline live:
classify -> reason (if ambiguous) -> act -> save to Supabase.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

from simulator import _make_event
from rules import classify_event
from reasoning import build_prompt, call_llm, parse_llm_response
from executor import execute_action

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def simulate_one_event():
    import random
    bucket = random.choice([
        "safe_retry", "late_auth", "no_retry",
        "cancelled", "escalate", "ambiguous",
    ])
    event = _make_event(bucket, running_id=9999)

    print(f"Generated event: {event['payment_id']} (bucket hint: {bucket})")

    classification, action_taken, reasoning, customer_message = classify_event(event)
    event["classification"] = classification
    print(f"Classified as: {classification}")

    if classification == "ambiguous":
        print("Ambiguous case -- calling LLM to reason...")
        prompt = build_prompt(event, customer_history=None)
        raw_response = call_llm(prompt)
        action, reasoning, customer_message = parse_llm_response(raw_response)
        event["action_taken"] = action
        event["reasoning"] = reasoning
        event["customer_message"] = customer_message
    else:
        event["action_taken"] = action_taken
        event["reasoning"] = reasoning
        event["customer_message"] = customer_message

    execution_note = execute_action(event)
    print(f"Action taken: {event.get('action_taken')}")
    print(f"Execution note: {execution_note}")

    client = get_supabase_client()
    client.table("payment_events").upsert(event, on_conflict="payment_id")
    print("Saved to Supabase. Check the dashboard -- it should appear within ~8s.")

    return event


if __name__ == "__main__":
    simulate_one_event()