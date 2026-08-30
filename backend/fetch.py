"""
Fetch real payment objects from Razorpay by ID.
Used to confirm actual field values (status, error_code, error_description,
error_source, error_step, error_reason) for both a captured and a failed
payment — these feed the action executor's real-API demo cases.
"""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

PAYMENT_IDS = {
    "captured": "pay_TUNS36yi8IUMUD",
    "failed": "pay_TUNUO8luY7klgB",
}


def fetch_payment(payment_id):
    url = f"https://api.razorpay.com/v1/payments/{payment_id}"
    response = requests.get(url, auth=(KEY_ID, KEY_SECRET))
    return response


if __name__ == "__main__":
    for label, payment_id in PAYMENT_IDS.items():
        print(f"=== {label.upper()}: {payment_id} ===")
        response = fetch_payment(payment_id)
        print("Status Code:", response.status_code)

        if response.status_code == 200:
            payment = response.json()
            for key, value in payment.items():
                print(f"  {key}: {value}")
        else:
            print("Something went wrong:", response.json())
        print()