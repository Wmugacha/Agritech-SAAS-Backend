import requests

BASE_URL = "http://localhost:8000/api"
EMAIL = "wilfredmugacha@gmail.com"
PASSWORD = "qwerty123456"

def get_token():
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"email": EMAIL, "password": PASSWORD})
    return resp.json()['access']

def test_stripe_checkout():
    print("--- 💳 Testing Stripe Integration (Day 13) ---")
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    print("\n1️⃣ Requesting a Stripe Checkout URL...")
    
    # Notice the URL matches the modular routing we just discussed!
    checkout_url = f"{BASE_URL}/subscriptions/checkout-session/"
    
    resp = requests.post(checkout_url, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        print("✅ Success! Stripe generated a checkout session.")
        print(f"🔗 Click here to pay: {data.get('checkout_url')}")
    else:
        print(f"❌ Failed to generate checkout session. Code: {resp.status_code}")
        print(f"Error Details: {resp.text}")

if __name__ == "__main__":
    test_stripe_checkout()