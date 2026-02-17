import requests
import time

BASE_URL = "http://localhost:8000/api"
EMAIL = "wilfredmugacha@gmail.com"
PASSWORD = "qwerty123456"

def get_token():
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"email": EMAIL, "password": PASSWORD})
    return resp.json()['access']

def run_end_to_end_analytics():
    print("--- 📊 Testing Analytics Engine (End-to-End) ---")
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a Farm
    print("\n1️⃣ Creating Farm & Field...")
    farm_resp = requests.post(f"{BASE_URL}/agronomy/farms/", headers=headers, json={
        "name": "Analytics Test Farm", "location": "Nairobi", "total_area_hectares": 50
    })
    farm_id = farm_resp.json()['id']

    # 2. Create a Field
    field_resp = requests.post(f"{BASE_URL}/agronomy/fields/", headers=headers, json={
        "farm": farm_id, "name": "Test Block A", "crop_type": "MAIZE", "area_hectares": 10
    })
    field_id = field_resp.json()['id']

    # 3. Submit a VALID Soil Test (2380 features so the ML model accepts it)
    print("2️⃣ Submitting valid Soil Test to Celery...")
    valid_spectra = [0.45] * 2380  # Simulating a flat absorbance line of 2380 features
    
    job_resp = requests.post(f"{BASE_URL}/predict/", headers=headers, json={
        "field": field_id,  # <--- LINKING THE JOB TO THE FIELD
        "spectra": valid_spectra
    })
    
    print("   ⏳ Waiting 3 seconds for Celery to process the ML Math...")
    time.sleep(3)

    # 4. Fetch the Analytics!
    print("\n3️⃣ Fetching Dashboard Aggregations...")
    analytics_resp = requests.get(f"{BASE_URL}/analytics/dashboard/", headers=headers)
    
    data = analytics_resp.json()
    print("✅ Analytics retrieved successfully!")
    print(f"   Total Samples (All Time): {data['total_samples_all_time']}")
    print(f"   Total Samples (This Month): {data['total_samples_this_month']}")
    print(f"   Average SOM: {data['average_som']}%")
    print(f"   Status Breakdown: {data['jobs_by_status']}")

if __name__ == "__main__":
    run_end_to_end_analytics()