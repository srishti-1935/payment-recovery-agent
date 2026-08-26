# PayResQ — AI-Powered Payment Recovery Agent

## The problem

When a UPI/card payment is disrupted mid-transaction, a customer's money can be
debited without the merchant's system getting clean confirmation. Razorpay calls
this a **late authorization** — the payment sits in an ambiguous state for up to
3 days before resolving. Naive systems either retry too early (risking a double
charge) or leave the customer anxious with no explanation.

This agent detects these ambiguous/failed payment states, reasons about the
right response per case (retry, wait-and-reassure, capture, escalate), executes
it against Razorpay's test-mode API, and logs every decision for a full audit
trail.

## Status

🚧 Early build — currently exploring Razorpay's test-mode API and real
payment/error object shapes before building the classification and reasoning
layers.

## Stack

- Backend: Python + FastAPI
- Frontend: React
- Payments: Razorpay test-mode API
- Reasoning: LLM API (used selectively, only for ambiguous cases)
- Audit log: SQLite

## Setup

1. Clone the repo
2. `cd backend && python -m venv venv`
3. Activate the virtual environment
4. `pip install -r requirements.txt` (coming soon)
5. Create a `.env` file with your own Razorpay test keys:
   RAZORPAY_KEY_ID=your_key_here
   RAZORPAY_KEY_SECRET=your_secret_here
