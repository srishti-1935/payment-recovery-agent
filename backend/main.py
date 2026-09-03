"""
Minimal FastAPI server with one job: receive real Razorpay webhook events,
verify they're genuinely from Razorpay, run them through the existing
pipeline (classify -> reason -> act), and save the result to Supabase.
"""

import os
import hmac
import hashlib
import json

from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from supabase import create_client

from rules import classify_event
from reasoning import build_prompt, call_llm, parse_llm_response
from executor import execute_action

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

app = FastAPI()


def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def verify_signature(raw_body: bytes, received_signature: str) -> bool:
    expected_signature = hmac.new(
        key=RAZORPAY_WEBHOOK_SECRET.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, received_signature)


@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_signature(raw_body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(raw_body)
    payment_entity = payload["payload"]["payment"]["entity"]

    event = {
        "payment_id": payment_entity["id"],
        "amount": payment_entity["amount"],
        "status": payment_entity["status"],
        "error_code": payment_entity.get("error_code"),
        "error_description": payment_entity.get("error_description"),
        "error_reason": payment_entity.get("error_reason"),
        "customer_id": payment_entity.get("email") or payment_entity.get("contact"),
        "retry_count": 0,
    }

    classification, action_taken, reasoning, customer_message = classify_event(event)
    event["classification"] = classification

    if classification == "ambiguous":
        prompt = build_prompt(event, customer_history=None)
        raw_response = call_llm(prompt)
        action_taken, reasoning, customer_message = parse_llm_response(raw_response)

    event["action_taken"] = action_taken
    event["reasoning"] = reasoning
    event["customer_message"] = customer_message

    execution_note = execute_action(event)
    print(f"Webhook processed: {event['payment_id']} -> {execution_note}")

    client = get_supabase_client()
    client.table("payment_events").upsert(event, on_conflict="payment_id").execute()

    return {"status": "processed", "payment_id": event["payment_id"]}


@app.get("/")
def health_check():
    return {"status": "ok"}