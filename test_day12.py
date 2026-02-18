import requests
import time
import csv
import os

BASE_URL = "http://localhost:8000/api"
EMAIL = "wilfredmugacha@gmail.com"
PASSWORD = "qwerty123456"

def get_token():
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"email": EMAIL, "password": PASSWORD})
    return resp.json()['access']

def test_csv_upload():
    print("--- 📂 Testing Real-World Data Ingestion (Day 12) ---")
    
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a fake CSV file that mimics a spectrometer
    print("\n1️⃣ Generating test_spectra.csv with 2380 values...")
    file_name = "test_spectra.csv"
    valid_spectra = [0.45] * 2380
    
    with open(file_name, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(valid_spectra) # Write as a single row

    # 2. Get a Field ID (We'll just grab the first farm/field available)
    print("2️⃣ Fetching a Field ID...")
    farm_resp = requests.get(f"{BASE_URL}/agronomy/fields/", headers=headers)
    if not farm_resp.json():
        print("❌ No fields found! Please run test_day11.py first to generate a field.")
        return
    field_id = farm_resp.json()[0]['id']

    # 3. Upload the CSV File using multipart/form-data
    print("3️⃣ Uploading CSV file to the API...")
    
    with open(file_name, 'rb') as f:
        # Note: We do NOT use 'json=' here. We use 'data=' for normal fields and 'files=' for the file
        payload_data = {"field": field_id}
        payload_files = {"spectra_file": (file_name, f, "text/csv")}
        
        # Remove Content-Type from headers so requests can set the multipart boundary automatically
        upload_headers = {"Authorization": f"Bearer {token}"}
        
        resp = requests.post(
            f"{BASE_URL}/predict/", # Replace with your exact prediction URL
            headers=upload_headers, 
            data=payload_data, 
            files=payload_files
        )

    if resp.status_code == 201:
        job_id = resp.json()['id']
        print(f"✅ File uploaded successfully! Job ID: {job_id}")
        
        print("   ⏳ Waiting 3 seconds for Celery to process the file data...")
        time.sleep(3)
        
        # Check if Celery successfully processed the parsed CSV data
        check_resp = requests.get(f"{BASE_URL}/predict/{job_id}/", headers=headers)
        print(f"✅ Final Job Status: {check_resp.json()['status']}")
        
    else:
        print(f"❌ File upload failed! Code: {resp.status_code}")
        print(resp.text)

    # Cleanup
    os.remove(file_name)

if __name__ == "__main__":
    test_csv_upload()