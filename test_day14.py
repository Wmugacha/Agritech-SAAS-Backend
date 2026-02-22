import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api"
EMAIL = "wilfredmugacha@gmail.com"
PASSWORD = "qwerty123456"

def print_step(title):
    print(f"\n{'-'*50}")
    print(f"🚀 {title}")
    print(f"{'-'*50}")

def run_timeline_test():
    print_step("Agritech Season & Activity Integration Test")
    
    # 1. Authenticate
    login_resp = requests.post(f"{BASE_URL}/auth/login/", json={
        "email": EMAIL,
        "password": PASSWORD
    })
    
    if login_resp.status_code != 200:
        print("❌ Login failed! Check credentials.")
        print(login_resp.json())
        return
        
    access_token = login_resp.json().get("access")
    headers = {"Authorization": f"Bearer {access_token}"}
    print("✅ Successfully authenticated!")

    # 2. Find or Create a Field
    print_step("Finding or Creating a Farm and Field")
    fields_resp = requests.get(f"{BASE_URL}/agronomy/fields/", headers=headers)
    
    if fields_resp.status_code == 200 and len(fields_resp.json()) > 0:
        target_field = fields_resp.json()[0]
        field_id = target_field['id']
        print(f"✅ Found existing Field: {target_field['name']} (ID: {field_id})")
    else:
        print("⚠️ No owned fields found. Creating a fresh Farm and Field to test RBAC...")
        
        # 2a. Create Farm
        farm_resp = requests.post(f"{BASE_URL}/agronomy/farms/", headers=headers, json={
            "name": "Test Cooperative Farm",
            "location": "Rift Valley",
            "total_area_hectares": "50.00"
        })
        
        if farm_resp.status_code != 201:
            print("❌ Failed to create Farm.")
            print(farm_resp.json())
            return
            
        farm_id = farm_resp.json()['id']
        print(f"✅ Created fresh Farm (ID: {farm_id})")
        
        # 2b. Create Field
        field_resp = requests.post(f"{BASE_URL}/agronomy/fields/", headers=headers, json={
            "farm": farm_id,
            "name": "Plot A",
            "crop_type": "MAIZE",
            "area_hectares": "10.00",
            "latitude": "-1.2921",
            "longitude": "36.8219"
        })
        
        if field_resp.status_code != 201:
            print("❌ Failed to create Field.")
            print(field_resp.json())
            return
            
        field_id = field_resp.json()['id']
        print(f"✅ Created fresh Field (ID: {field_id})")

    # 3. Create a Crop Season
    print_step("Creating a new Crop Season (Maize)")
    season_payload = {
        "field": field_id,
        "crop_type": "MAIZE",
        "season_name": "Long Rains 2026",
        "status": "GROWING",
        "planting_date": "2026-03-01",
        "target_yield_kg": "4500.00"
    }
    
    season_resp = requests.post(f"{BASE_URL}/agronomy/seasons/", json=season_payload, headers=headers)
    
    if season_resp.status_code != 201:
        print("❌ Failed to create Crop Season.")
        print(season_resp.json())
        return
        
    season_data = season_resp.json()
    season_id = season_data['id']
    print(f"✅ Created Season: {season_data['season_name']} (ID: {season_id})")

    # 4. Log a Farm Activity (Fertilizer)
    print_step("Logging a Farm Activity (Fertilizer Application)")
    activity_payload = {
        "season": season_id,
        "activity_type": "FERTILIZER",
        "activity_date": datetime.now().strftime("%Y-%m-%d"),
        "description": "Applied 50kg of CAN Nitrogen fertilizer to boost early growth.",
        "cost": "3500.00"
    }
    
    activity_resp = requests.post(f"{BASE_URL}/agronomy/activities/", json=activity_payload, headers=headers)
    
    if activity_resp.status_code != 201:
        print("❌ Failed to create Farm Activity.")
        print(activity_resp.json())
        return
        
    activity_data = activity_resp.json()
    print(f"✅ Logged Activity: {activity_data['activity_type']} - Cost: KES {activity_data['cost']}")

    # 5. Verify the Nested Timeline
    print_step("Verifying the full timeline API response")
    verify_resp = requests.get(f"{BASE_URL}/agronomy/seasons/{season_id}/", headers=headers)
    
    if verify_resp.status_code == 200:
        final_data = verify_resp.json()
        print("✅ Season details successfully retrieved!")
        print(f"Total Activities tracked: {len(final_data.get('activities', []))}")
        print("\nFull JSON Response:")
        print(json.dumps(final_data, indent=2))
    else:
        print("❌ Failed to fetch the final nested season data.")

if __name__ == "__main__":
    run_timeline_test()