"""
Step 1: We are simply checking razorpay's test api key and what an actual order object looks like
"""

import os
import requests
from dotenv import load_dotenv
load_dotenv()

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    raise SystemExit(
        "Could not find RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET.\n"
        "Check if your env file exists in this folder and has both the required values."
    )
url = "https://api.razorpay.com/v1/orders"

payload = {
    "amount" : 50000,
    "currency" : "INR",
    "receipt" : "explore_test_1",
}

response = requests.post(url, json=payload, auth=(KEY_ID, KEY_SECRET))  
print("Status Code:", response.status_code)
print()

if response.status_code == 200:
    order = response.json()
    print("Order created successfully! Here are the real fields returned by Razorpay:")
    print()

    for key, value in order.items():
        print(f" {key}: {value}")
else:
    print("Something went wrong. Here is the response from Razorpay:")
    print(response.json())
    