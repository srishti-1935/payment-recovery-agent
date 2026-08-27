import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")

supabase = create_client(url, key)

test_row = {
    "payment_id": "test_pay_001",
    "amount": 50000,
    "status": "failed",
    "error_code": "gateway_technical_error",
    "error_description": "test row - safe to delete",
    "error_reason": "gateway_technical_error",
    "customer_id": "test_cus_001",
    "retry_count": 0,
    "classification": "safe_retry",
    "action_taken": "auto_retry",
    "reasoning": "manual connection test"
}
result = supabase.table("payment_events").insert(test_row).execute()    
print(result)