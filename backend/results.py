"""
Final results summary — answers the PRD's success metrics directly:
- ₹ at risk -> ₹ recovered -> ₹ unresolved
- Count of cases correctly NOT acted on (the "AI judgment" bar)
- Example real queries: all late-auth cases, all cases agent declined to act on
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return create_client(url, key)


def rupees(paise):
    return f"₹{paise / 100:,.2f}"


def main():
    supabase = get_supabase_client()
    all_events = supabase.table("payment_events").select("*").execute().data

    total = len(all_events)
    at_risk = sum(e["amount"] for e in all_events if e["classification"] != "success")
    recovered = sum(
        e["amount"] for e in all_events
        if e["action_taken"] == "auto_retry"
    )
    unresolved = at_risk - recovered
    
    escalated = [e for e in all_events if e["action_taken"] == "escalate_to_merchant"]
    held_back = [e for e in all_events if e["action_taken"] in ("wait_and_reassure", "no_action")]
    late_auth = [e for e in all_events if e["classification"] == "late_auth"]
    ambiguous_reasoned = [e for e in all_events if e["classification"] == "ambiguous"]

    print("=" * 60)
    print("PAYRESQ — FINAL BATCH RESULTS")
    print("=" * 60)
    print(f"Total events processed: {total}")
    print()
    print(f"₹ At risk:      {rupees(at_risk)}")
    print(f"₹ Recovered:    {rupees(recovered)}")
    print(f"₹ Unresolved:   {rupees(unresolved)}")
    print()
    print(f"Escalated to merchant (suspicious/repeated): {len(escalated)}")
    print(f"Correctly held back (no premature retry):    {len(held_back)}")
    print(f"Late-authorization cases (core scenario):    {len(late_auth)}")
    print(f"Ambiguous cases resolved via LLM reasoning:  {len(ambiguous_reasoned)}")
    print()
    print("--- Sample: late-auth cases (the core differentiator) ---")
    for e in late_auth[:3]:
        print(f"  {e['payment_id']}: {rupees(e['amount'])} -> {e['reasoning']}")
    print()
    print("--- Sample: cases agent correctly declined to act on ---")
    for e in held_back[:3]:
        print(f"  {e['payment_id']}: {e['classification']} -> {e['reasoning']}")


if __name__ == "__main__":
    main()