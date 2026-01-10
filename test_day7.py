import requests
import pandas as pd
import time
import json

# CONFIG
BASE_URL = "http://localhost:8000/api"
CSV_PATH = "soil_data.xlsx"
EMAIL = "wilfredmugacha@gmail.com"
PASSWORD = "qwerty123456"

def get_auth_token():
    """Login and get JWT"""
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"email": EMAIL, "password": PASSWORD})
    if resp.status_code != 200:
        print("❌ Login Failed:", resp.text)
        exit()
    return resp.json()['access']

def run_simulation():
    print("--- 🚀 Starting Prediction Task ---")
    
    # 1. Load Data
    print(f"📂 Loading CSV: {CSV_PATH}")
    df = pd.read_excel(CSV_PATH)
    
    # Take the first row
    row = df.iloc[0]
    real_som = row['SOM']
    
    # STRIP the SOM (Answer) and keep only Spectra (Questions)
    spectra_data = row.iloc[1:].tolist()
    
    print(f"📊 Extracted {len(spectra_data)} spectral points.")
    print(f"🤫 Hiding Real SOM: {real_som}")

    # 2. Authenticate
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 3. Send Prediction Request
    payload = {"spectra": spectra_data}
    print("📡 Sending Request to API...")
    
    start_time = time.time()
    resp = requests.post(f"{BASE_URL}/predict/", headers=headers, json=payload)
    
    if resp.status_code != 201:
        print("❌ Prediction Request Failed:", resp.text)
        exit()
        
    job_id = resp.json()['id']
    print(f"✅ Job Created! ID: {job_id}")
    print("⏳ Waiting for Async Worker...")

    # 4. Poll for Result
    for _ in range(10): # Try 10 times (10 seconds)
        time.sleep(1)
        status_resp = requests.get(f"{BASE_URL}/predict/{job_id}/", headers=headers)
        job_data = status_resp.json()
        status = job_data['status']
        print(f"   Status: {status}")
        
        if status == "SUCCESS":
            result = job_data['predicted_properties']
            print("\n🎉 SUCCESS!")
            print(f"🔮 API Predicted: {result}")
            print(f"🧪 Lab Value:    {real_som}")
            print(f"⏱️ Total Time:   {round(time.time() - start_time, 2)}s")
            return
        elif status == "FAILED":
            print("❌ Job Failed:", job_data.get('error_message'))
            return

    print("⚠️ Timed out waiting for result.")

if __name__ == "__main__":
    run_simulation()