"""
Razorpay card payment error codes, organized by classification bucket.
Source: https://razorpay.com/docs/errors/payments/cards/
Each entry: error_code -> (error_description, error_reason, bucket)
"""

ERROR_CODES = {
    # Bucket 1 - Safe to auto-retry (not a customer mistake but a tech issue)
        "gateway_technical_error": {
        "description": "There was a downtime on our partner bank due to which the payment has failed.",
        "reason": "gateway_technical_error",
        "bucket": "safe_retry",
    },
    "bank_technical_error": {
        "description": "There was a downtime on the customer's bank due to which the payment has failed.",
        "reason": "bank_technical_error",
        "bucket": "safe_retry",
    },

    # Bucket 2 - Late authorization (special case: wait and don't retry in panic)
    "payment_timed_out": {
        "description": "The payment could not be completed as the customer exceeded the time limit for payment processing. This time limit is typically 10 minutes unless otherwise specified.",
        "reason": "payment_timed_out",
        "bucket": "late_auth",
    },

    # Bucket 3 - No retry, customer has to act
    "insufficient_funds": {
        "description": "The payment could not be completed the customer's bank account does not have sufficient funds for the transaction.",
        "reason": "insufficient_funds",
        "bucket": "no_retry",
    },
    "card_expired": {
        "description": "The payment could not be completed because the customer's card has expired.",
        "reason": "card_expired",
        "bucket": "no_retry",
    },
    "debit_instrument_blocked": {
        "description": "The payment could not be processed because the customer's card has been blocked, either by the customer or the bank.",
        "reason": "debit_instrument_blocked",
        "bucket": "no_retry",
    },
    "card_not_enrolled": {
        "description": "The payment was unsuccessful as the card was not activated or enabled by the customer for online transactions.",
        "reason": "card_not_enrolled",
        "bucket": "no_retry",
    },
    "card_disabled_for_online_payments": {
        "description": "The payment was unsuccessful as the card was not activated or enabled by the customer for online transactions.",
        "reason": "card_disabled_for_online_payments",
        "bucket": "no_retry",
    },
    "debit_instrument_inactive": {
        "description": "The payment was unsuccessful as the card was not activated or enabled by the customer for online transactions.",
        "reason": "debit_instrument_inactive",
        "bucket": "no_retry",
    },
    "incorrect_cvv": {
        "description": "The payment was unsuccessful as the customer entered an incorrect CVV during the payment process.",
        "reason": "incorrect_cvv",
        "bucket": "no_retry",
    },
    "authentication_failed": {
        "description": "The payment did not go through as the customer entered incorrect OTP/verification details or accidentally closed the browser/pressed the back button during the authentication stage of the transaction.",
        "reason": "authentication_failed",
        "bucket": "no_retry",
    },
    "transaction_limit_exceeded": {
        "description": "The payment did not go through because the customer has already reached the maximum transaction limit on their card for the day.",
        "reason": "transaction_limit_exceeded",
        "bucket": "no_retry",
    },

    # Bucket 4 - Customer does not want to pay, leave it
    "payment_cancelled": {
        "description": "The payment could not be completed as the customer cancelled the transaction or pressed the back button during th epayment processing period.",
        "reason": "payment_cancelled",
        "bucket": "cancelled",
    },

    # Bucket 5 - Suspicious, escalate, DO NOT touch
    "payment_risk_check_failed": {
        "description": "The transaction was unsuccessful as the customer's bank declined the payment, labeling it as a fraudulent.",
        "reason": "payment_risk_check_failed",
        "bucket": "escalate",
    },

    # Bucket 6 - Ambiguous, needs the AI/LLM to reason about it
    "card_declined": {
        "description": "The payment was declined by the customer's bank, resulting in the trasnaction being unsucessful.",
        "reason": "card_declined",
        "bucket": "ambiguous",
    },
    "payment_failed": {
        "description": "The payment was declined by the customer's bank, resulting in the transaction being unsucessful.",
        "reason": "payment_failed",
        "bucket": "ambiguous",
    },

}

# Convenience: bucket -> list of error codes (derived from ERROR_CODES, do not maintain separately)
BUCKET_CODES = {}
for code, info in ERROR_CODES.items():
    BUCKET_CODES.setdefault(info["bucket"], []).append(code)
