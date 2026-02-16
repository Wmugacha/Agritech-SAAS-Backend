import requests
import time

BASE_URL = "http://localhost:8000/api"
EMAIL = "wilfredmugacha@gmail.com"
PASSWORD = "qwerty123456"

def get_token():
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"email": EMAIL, "password": PASSWORD})
    return resp.json()['access']

def test_contract():
    print("--- 📜 Testing API Contract (Day 10) ---")
    
    # 1. Check Documentation
    print("\n1️⃣  Checking Swagger Docs...")
    resp = requests.get(f"http://localhost:8000/api/docs/")
    if resp.status_code == 200:
        print("✅ Swagger UI is live.")
    else:
        print(f"❌ Swagger missing: {resp.status_code}")

    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 2. TIER 1: Test Bad Input (Strings)
    print("\n2️⃣  Testing Tier 1 Validation (Strings)...")
    bad_payload = {"spectra": ["garbage", "data"]}
    resp = requests.post(f"{BASE_URL}/predict/", headers=headers, json=bad_payload)
    
    if resp.status_code == 400:
        print(f"✅ Gateway blocked strings: {resp.json()}")
    else:
        print(f"❌ Gateway failed! Code: {resp.status_code}")

    # 3. TIER 1: Test Empty List
    print("\n3️⃣  Testing Tier 1 Validation (Empty List)...")
    empty_payload = {"spectra": []}
    resp = requests.post(f"{BASE_URL}/predict/", headers=headers, json=empty_payload)
    
    if resp.status_code == 400:
        print(f"✅ Gateway blocked empty list: {resp.json()}")
    else:
        print(f"❌ Gateway failed! Code: {resp.status_code}")

    # 4. TIER 2: Test Scientific Validation (Shape Mismatch)
    print("\n4️⃣  Testing Tier 2 Validation (Shape Mismatch)...")
    # Sending 3 features. The model likely expects ~1700.
    wrong_shape_payload = {"spectra": [1.0, 2.0, 3.0]}
    
    # The API should ACCEPT it (Structural validation passes)
    resp = requests.post(f"{BASE_URL}/predict/", headers=headers, json=wrong_shape_payload)
    
    if resp.status_code == 201:
        job_id = resp.json()['id']
        print(f"✅ Gateway accepted structure (201). Job ID: {job_id}")
        
        # Now let's wait a second and ask the database what Celery did with it
        print("   ⏳ Waiting for Celery to process...")
        time.sleep(2) 
        
        check_resp = requests.get(f"{BASE_URL}/predict/{job_id}/", headers=headers)
        job_data = check_resp.json()
        
        if job_data['status'] == 'FAILED':
            print(f"✅ Celery correctly FAILED the job! Reason: {job_data['error_message']}")
            print(f"✅ User Refunded? (is_billable): {job_data['is_billable']}")
        else:
            print(f"❌ Celery did not fail! Status: {job_data['status']}")
            
    else:
        print(f"❌ API behaved unexpectedly: Code {resp.status_code}")

if __name__ == "__main__":
    test_contract()