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

✅ Full pipeline built and working end-to-end: simulate → classify → reason →
execute → dashboard. Validated against both an 80-event simulated batch and 2
real Razorpay test-mode payments.

**Built:**
- Explored Razorpay's test-mode API: created real orders, triggered and
  inspected both a successful and a failed test payment to confirm the real
  object shape (`status`, `error_code`, `error_description`, `error_source`,
  `error_step`, `error_reason`)
- Classified Razorpay's 16 documented card error codes into action buckets:
  safe-to-retry, late-authorization (the core case this project targets),
  no-retry/customer-must-act, cancelled, escalate, and ambiguous-needs-reasoning
- Batch simulator: generates 80 realistic mock payment events across all
  buckets, including repeat-customer edge cases
- Rules layer: deterministically classifies every non-ambiguous case and
  writes classification/action/reasoning to the audit log
- Reasoning layer: LLM call (via OpenRouter) for ambiguous cases only, using
  error context + retry_count + customer history, with explicit decision
  rules to ensure genuinely differentiated judgment (see Results below)
- Action executor: verifies real payment state via the Razorpay API for live
  test payments, logs intended actions for simulated ones, with a
  double-execution guard (`executed_at` timestamp)
- React dashboard: live summary metrics and a batch table with expandable
  per-payment reasoning, polling Supabase every 8s
- Supabase (Postgres) as the audit log — every decision traceable by
  payment ID, classification, action, and reasoning

**Not yet done:** demo video, stuck-refunds bonus flow (optional per PRD).

## Results (full batch run)

Ran the complete pipeline on an 82-event batch — 80 simulated Razorpay-style
payment events plus 2 real Razorpay test-mode payments verified live via the
API.

- **₹ At risk:** ₹1,30,906.13
- **₹ Recovered** (safely auto-retried): ₹21,139.18
- **₹ Unresolved** (correctly held for customer action, escalation, or
  late-auth wait): ₹1,09,766.95
- **Escalated to merchant for human review:** 4 cases
- **Correctly held back from acting** (no premature retry — late-auth waits
  + customer cancellations): 13 cases
- **Late-authorization cases handled** (the core scenario this project
  targets): 8
- **Ambiguous cases resolved via LLM reasoning** (not deterministic rules):
  10, including 1 real Razorpay test payment

The reasoning layer was validated against a genuine issue during
development: an early prompt version caused every ambiguous case to default
to the same action regardless of context. Adding explicit decision rules
(retry_count and customer-history thresholds) to the prompt fixed this — the
batch now shows differentiated outcomes (e.g. a payment with `retry_count=2`
correctly escalates, while a first-time decline with no history correctly
routes to customer notification).

## Stack

- **Backend:** Python + FastAPI
- **Frontend:** React (Vite)
- **Payments:** Razorpay test-mode API
- **Reasoning:** LLM API via OpenRouter (used selectively, only for
  ambiguous cases)
- **Audit log:** Supabase (Postgres) — chosen over SQLite for real-time
  querying and a ready-made table viewer for inspecting decisions

## Setup

### Backend
1. Clone the repo
2. `cd backend && python -m venv venv`
3. Activate the virtual environment
4. `pip install requests python-dotenv fastapi uvicorn supabase`
5. Create a `.env` file in `backend/` with:
   - `RAZORPAY_KEY_ID=your_key_here`
   - `RAZORPAY_KEY_SECRET=your_secret_here`
   - `SUPABASE_URL=your_supabase_project_url`
   - `SUPABASE_ANON_KEY=your_supabase_anon_key`
   - `OPENROUTER_API_KEY=your_openrouter_key`
   
   (Never use the Supabase `service_role` key here — treat it with the same care as Razorpay secret.)
6. In your Supabase dashboard, create a `payment_events` table (see schema
   below) and enable Row Level Security policies allowing `SELECT`,
   `INSERT`, and `UPDATE` for the `anon` role — RLS is on by default and
   blocks all access until explicitly allowed.
7. Run the pipeline in order: `python simulator.py` → `python rules.py` → `python reasoning.py` → `python executor.py` → `python results.py`


### Frontend
1. `cd frontend && npm install`
2. Create a `.env` file in `frontend/` with:
   - `VITE_SUPABASE_URL=your_supabase_project_url`
   - `VITE_SUPABASE_ANON_KEY=your_supabase_anon_key`
3. `npm run dev`

### Database schema (`payment_events` table)
`payment_id`, `amount`, `status`, `error_code`, `error_description`,
`error_reason`, `customer_id`, `retry_count`, `classification`,
`action_taken`, `reasoning`, `executed_at`, plus auto `id`/`created_at`.