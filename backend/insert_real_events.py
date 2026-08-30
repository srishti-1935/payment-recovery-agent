"""
One-off: insert the real Razorpay test payments into payment_events,
so they flow through the same rules/reasoning/executor pipeline as
the simulated batch.
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY"))

real_events = [
    {
        "payment_id": "pay_TUNS36yi8IUMUD",
        "amount": 50000,
        "status": "captured",
        "error_code": None,
        "error_description": None,
        "error_reason": None,
        "customer_id": "cust_real_001",
        "retry_count": 0,
        "classification": None,
        "action_taken": None,
        "reasoning": None,
    },
    {
        "payment_id": "pay_TUNUO8luY7klgB",
        "amount": 50000,
        "status": "failed",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Your payment didn't go through as it was declined by the bank. Try another payment method or contact your bank.",
        "error_reason": "payment_failed",
        "customer_id": "cust_real_002",
        "retry_count": 0,
        "classification": None,
        "action_taken": None,
        "reasoning": None,
    },
]

result = supabase.table("payment_events").insert(real_events).execute()
print(f"Inserted {len(result.data)} real payment rows")