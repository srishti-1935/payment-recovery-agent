"""
Step 2: Fetch a real payment object by using its ID!
"""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

PAYMENT_ID="pay_TUNItow6OovI0z"
url= f"https://api.razorpay.com/v1/payments/{PAYMENT_ID}"
response = requests.get(url, auth=(KEY_ID, KEY_SECRET))

print("Status Code:", response.status_code)
print()

if response.status_code == 200:
    payment = response.json()
    print("Here is the real payment object:")
    print()
    for key, value in payment.items():
        print(f" {key}: {value}")

else:
    print("Something went wrong:")
    print(response.json())

