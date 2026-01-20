import requests
import json

# CONFIG
BASE_URL = "http://localhost:8000/api"
EMAIL = "wilfredmugacha@gmail.com"      # Ensure this user is in an Organization
PASSWORD = "qwerty123456"

def get_auth_token():
    print(f"🔑 Logging in as {EMAIL}...")
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"email": EMAIL, "password": PASSWORD})
    if resp.status_code != 200:
        print("❌ Login Failed:", resp.text)
        exit()
    return resp.json()['access']

def run_agronomy_simulation():
    print("--- 🚜 Starting Day 9 Simulation (Farm & Field) ---")
    
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Create a Farm
    # ---------------------------------------------------------
    print("\n1️⃣  Creating a Farm...")
    farm_payload = {
        "name": "Rift Valley Highland Estate",
        "location": "Nakuru, Kenya",
        "total_area_hectares": 50.0
    }
    
    resp = requests.post(f"{BASE_URL}/agronomy/farms/", headers=headers, json=farm_payload)
    
    if resp.status_code != 201:
        print("❌ Create Farm Failed:", resp.text)
        return

    farm_data = resp.json()
    farm_id = farm_data['id']
    print(f"✅ Farm Created! ID: {farm_id}")
    print(f"   Owner: {farm_data.get('owner', 'Unknown')}")

    # 2. Create a Field inside that Farm
    # ---------------------------------------------------------
    print(f"\n2️⃣  Adding a Field to Farm {farm_id}...")
    field_payload = {
        "farm": farm_id,
        "name": "Block A - Maize",
        "crop_type": "MAIZE",
        "area_hectares": 12.5,
        "latitude": -0.3031,  # Example coords near Nakuru
        "longitude": 36.0800
    }

    resp = requests.post(f"{BASE_URL}/agronomy/fields/", headers=headers, json=field_payload)

    if resp.status_code != 201:
        print("❌ Create Field Failed:", resp.text)
        return

    field_data = resp.json()
    field_id = field_data['id']
    print(f"✅ Field Created! ID: {field_id}")
    print(f"   Crop: {field_data['crop_type']}")

    # 3. Verify Visibility (List Farms)
    # ---------------------------------------------------------
    print("\n3️⃣  Verifying Visibility...")
    resp = requests.get(f"{BASE_URL}/agronomy/farms/", headers=headers)
    farms = resp.json()
    print(f"✅ User can see {len(farms)} farm(s).")
    
    print("\n🎉 Day 9 Simulation Complete.")

if __name__ == "__main__":
    run_agronomy_simulation()