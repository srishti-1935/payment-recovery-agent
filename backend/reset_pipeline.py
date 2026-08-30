import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY"))

all_events = supabase.table("payment_events").select("payment_id").execute().data
print(f"Resetting {len(all_events)} rows...")

for e in all_events:
    supabase.table("payment_events").update({
        "classification": None,
        "action_taken": None,
        "reasoning": None,
        "customer_message": None,
        "executed_at": None,
    }).eq("payment_id", e["payment_id"]).execute()

print("Done.")