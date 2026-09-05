"""
FastAPI server with two jobs:
1. Receive real Razorpay webhook events, verify signature, run them through
   the pipeline (classify -> reason -> act), save to Supabase.
2. Expose a /simulate-event endpoint so the live dashboard can trigger a
   single payment event on demand and see the pipeline run in real time.
"""

import os
import hmac
import hashlib
import json
import random
import string

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client

from rules import classify_event
from reasoning import build_prompt, call_llm, parse_llm_response
from executor import execute_action
from error_codes import ERROR_CODES

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel URL before final submission if you want
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def verify_signature(raw_body: bytes, received_signature: str) -> bool:
    expected_signature = hmac.new(
        key=RAZORPAY_WEBHOOK_SECRET.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, received_signature)


def _random_id(prefix, length=8):
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}_{suffix}"


def run_pipeline_on_event(event: dict) -> dict:
    """Shared pipeline logic: classify -> reason (if ambiguous) -> act -> save."""
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
    print(f"Processed: {event['payment_id']} -> {execution_note}")

    client = get_supabase_client()
    client.table("payment_events").upsert(event, on_conflict="payment_id").execute()

    return event


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

    result = run_pipeline_on_event(event)
    return {"status": "processed", "payment_id": result["payment_id"]}


class SimulateRequest(BaseModel):
    amount: int  # in paise
    error_code: str | None = None  # if None, simulates a successful payment


@app.post("/simulate-event")
def simulate_event(req: SimulateRequest):
    payment_id = _random_id("pay_live")
    customer_id = _random_id("cust_live")

    if req.error_code is None:
        event = {
            "payment_id": payment_id,
            "amount": req.amount,
            "status": "captured",
            "error_code": None,
            "error_description": None,
            "error_reason": None,
            "customer_id": customer_id,
            "retry_count": 0,
        }
    else:
        if req.error_code not in ERROR_CODES:
            raise HTTPException(status_code=400, detail=f"Unknown error_code: {req.error_code}")
        error_info = ERROR_CODES[req.error_code]
        event = {
            "payment_id": payment_id,
            "amount": req.amount,
            "status": "created" if error_info["bucket"] == "late_auth" else "failed",
            "error_code": req.error_code,
            "error_description": error_info["description"],
            "error_reason": error_info["reason"],
            "customer_id": customer_id,
            "retry_count": 0,
        }

    result = run_pipeline_on_event(event)
    return result


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/error-codes")
def list_error_codes():
    """Lets the frontend populate a dropdown of real error codes to test with."""
    return {code: info["bucket"] for code, info in ERROR_CODES.items()}