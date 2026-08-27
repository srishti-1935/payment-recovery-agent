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

🚧 In progress — API exploration and error classification complete, now
building the batch simulator and reasoning layers.

Done so far:
- Explored Razorpay's test-mode API: created real orders, triggered and
  inspected both a successful and a failed test payment to confirm the real
  object shape (`status`, `error_code`, `error_description`, `error_source`,
  `error_step`, `error_reason`)
- Pulled Razorpay's documented card payment error codes and classified all
  16 into action buckets: safe-to-retry, late-authorization (the core case
  this project targets), no-retry/customer-must-act, cancelled, escalate,
  and ambiguous-needs-reasoning
- Set up Supabase (Postgres) as the audit log, with the `payment_events`
  table live and a verified read/write connection

Not yet built: batch simulator, rules layer, reasoning layer, action
executor, dashboard.

## Stack

- Backend: Python + FastAPI
- Frontend: React
- Payments: Razorpay test-mode API
- Reasoning: LLM API (used selectively, only for ambiguous cases)
- Audit log: Supabase (Postgres) — chosen over SQLite for real-time
  subscriptions (dashboard updates without polling) and easier querying

## Setup

1. Clone the repo
2. `cd backend && python -m venv venv`
3. Activate the virtual environment
4. `pip install -r requirements.txt` (coming soon)
5. Create a `.env` file with your own Razorpay test keys:
   RAZORPAY_KEY_ID=your_key_here
   RAZORPAY_KEY_SECRET=your_secret_here
6. Also add your Supabase project URL and anon public key to `.env`:
   SUPABASE_URL=your_project_url_here
   SUPABASE_KEY=your_anon_public_key_here

   (Never use the `service_role` key here — treat it with the same care as
   the Razorpay secret.)
7. In your Supabase dashboard, make sure Row Level Security policies allow
   `INSERT` and `SELECT` for the `anon` role on the `payment_events` table
   (Table Editor → your table → Policies). RLS is on by default and blocks
   all access until explicitly allowed.
