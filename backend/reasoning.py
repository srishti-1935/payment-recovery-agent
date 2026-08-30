"""
Reasoning layer — handles the 'ambiguous' payment events (card_declined,
payment_failed) that the rules layer couldn't classify deterministically.
Calls an LLM (via OpenRouter) with full context per case, gets back a
constrained action, an internal reasoning note, and a separate
customer-facing message, then writes all three back to Supabase.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "cohere/north-mini-code:free"

VALID_ACTIONS = [
    "auto_retry",
    "wait_and_reassure",
    "notify_customer_action_required",
    "escalate_to_merchant",
]


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return create_client(url, key)


def build_prompt(event, customer_history):
    history_text = "No other payment attempts from this customer in this batch."
    if customer_history:
        lines = [
            f"- {h['payment_id']}: status={h['status']}, error_code={h['error_code']}, classification={h.get('classification')}"
            for h in customer_history
        ]
        history_text = "Other payment events from this same customer in this batch:\n" + "\n".join(lines)

    return f"""You are a payment recovery agent reasoning about an ambiguous failed payment for Razorpay, an Indian payments platform.

Payment details:
- payment_id: {event['payment_id']}
- amount: ₹{event['amount'] / 100:.2f}
- error_code: {event['error_code']}
- error_description: {event['error_description']}
- retry_count so far: {event['retry_count']}

{history_text}

Context: "{event['error_code']}" is Razorpay's own catch-all decline code — it does not tell us the specific reason, unlike more specific codes (e.g. insufficient_funds, card_expired).

Decision guidance (apply these in order — retry_count and history should change your answer, not just the error_code):
1. If retry_count >= 2 OR this customer has 2+ other failed payments in their history above -> lean toward escalate_to_merchant (repeated failures are a pattern worth human review, not more automation).
2. If retry_count == 0 AND there is no concerning history -> a first-time generic decline is most often a customer-side issue -> notify_customer_action_required.
3. If retry_count == 1 with no other concerning history -> borderline: consider whether the description suggests a transient issue (auto_retry) vs a persistent one (notify_customer_action_required).
4. Only choose wait_and_reassure if something in the description or timing genuinely resembles a late-authorization / timeout pattern, not a bank decline.

Choose exactly ONE action from this list:
- auto_retry: safe to retry automatically (likely a transient/technical issue)
- wait_and_reassure: do NOT retry, this may resolve on its own like a late authorization (risk of double-charge if retried)
- notify_customer_action_required: likely a customer-side issue (card/funds/auth), retrying won't help
- escalate_to_merchant: repeated failures or suspicious pattern, needs human review

Respond with ONLY valid JSON, no other text, in this exact format:
{{"action": "one_of_the_four_options_above", "reasoning": "1-2 sentence explanation of your judgment for the merchant's internal audit log, mentioning what specifically drove the decision (cite the retry_count or history if it mattered)", "customer_message": "A short, warm, honest 1-2 sentence message to show the CUSTOMER directly. Do not mention internal reasoning, retry counts, or error codes. Just tell them clearly what's happening and what to expect next."}}"""


def call_llm(prompt, max_retries=3):
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    for attempt in range(max_retries):
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 429:
            wait = 5 * (attempt + 1)  # 5s, 10s, 15s
            print(f"    rate limited, waiting {wait}s before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait)
            continue

        if response.status_code != 200:
            print(f"    DEBUG - status {response.status_code}: {response.text}")

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    raise Exception(f"Rate limited after {max_retries} retries")


def parse_llm_response(raw_text):
    # Strip potential markdown code fences the model might add despite instructions
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    parsed = json.loads(cleaned)
    action = parsed.get("action")
    reasoning = parsed.get("reasoning", "").strip()
    customer_message = parsed.get("customer_message", "").strip()

    if action not in VALID_ACTIONS:
        raise ValueError(f"LLM returned invalid action: {action}")

    return action, reasoning, customer_message


def run_reasoning_layer(dry_run=False):
    supabase = get_supabase_client()

    response = supabase.table("payment_events").select("*").eq("classification", "ambiguous").execute()
    ambiguous_events = response.data
    print(f"Found {len(ambiguous_events)} ambiguous events to reason about")

    # Build a lookup of all events by customer_id, for history context
    all_response = supabase.table("payment_events").select("*").execute()
    all_events = all_response.data
    by_customer = {}
    for e in all_events:
        by_customer.setdefault(e["customer_id"], []).append(e)

    results = []
    for event in ambiguous_events:
        history = [
            h for h in by_customer.get(event["customer_id"], [])
            if h["payment_id"] != event["payment_id"]
        ]
        prompt = build_prompt(event, history)

        try:
            raw = call_llm(prompt)
            action, reasoning, customer_message = parse_llm_response(raw)
        except Exception as e:
            print(f"  ⚠️ {event['payment_id']}: LLM call/parse failed ({e}) — falling back to escalate_to_merchant")
            action = "escalate_to_merchant"
            reasoning = f"LLM reasoning failed ({type(e).__name__}), escalated for manual review as a safe default."
            customer_message = "We're reviewing this payment. Our team will follow up with you shortly."

        print(f"  {event['payment_id']} ({event['error_code']}, retry_count={event['retry_count']}) -> {action}")
        print(f"    reasoning: {reasoning}")
        print(f"    customer_message: {customer_message}")

        if not dry_run:
            supabase.table("payment_events").update({
                "action_taken": action,
                "reasoning": reasoning,
                "customer_message": customer_message,
            }).eq("payment_id", event["payment_id"]).execute()

        results.append((event["payment_id"], action, reasoning, customer_message))

        time.sleep(2)  # be polite to the shared free-tier pool

    if dry_run:
        print("\n(dry run — nothing written to Supabase)")

    return results


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    run_reasoning_layer(dry_run=dry_run)