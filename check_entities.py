#!/usr/bin/env python3
"""Check Sandsara entities in Home Assistant"""

import requests
import json

HA_URL = "http://192.168.0.171:8123"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI2NWFlMzExMzM3ZWY0ZDQwYmI2MTIyZjJmOWRiNjA4NSIsImlhdCI6MTc2OTQ3NDc0NSwiZXhwIjoyMDg0ODM0NzQ1fQ.wv2S2vt870VgGqEGGMeSyhd3LKGUxf4oGL5-XGshy3U"

headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "content-type": "application/json",
}

def get_sandsara_entities():
    """Get all Sandsara entities"""
    try:
        response = requests.get(f"{HA_URL}/api/states", headers=headers)
        if response.status_code == 200:
            states = response.json()
            sandsara_entities = [
                entity for entity in states 
                if entity["entity_id"].startswith("sandsara") or 
                   "sandsara" in entity["entity_id"] or
                   (entity.get("attributes", {}).get("integration") == "sandsara")
            ]
            
            print(f"Found {len(sandsara_entities)} Sandsara entities:")
            for entity in sandsara_entities:
                entity_id = entity["entity_id"]
                state = entity["state"]
                friendly_name = entity.get("attributes", {}).get("friendly_name", "")
                print(f"  - {entity_id}: {state} ({friendly_name})")
            
            return sandsara_entities
        else:
            print(f"✗ Failed to get states: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error getting entities: {e}")
        return []

def get_devices():
    """Get Sandsara devices"""
    try:
        response = requests.get(f"{HA_URL}/api/config/device_registry", headers=headers)
        if response.status_code == 200:
            devices = response.json()
            sandsara_devices = [
                device for device in devices 
                if any("sandsara" in ident for ident in device.get("identifiers", []))
                or "sandsara" in device.get("manufacturer", "").lower()
            ]
            
            print(f"\nFound {len(sandsara_devices)} Sandsara devices:")
            for device in sandsara_devices:
                name = device.get("name", "Unknown")
                model = device.get("model", "Unknown")
                manufacturer = device.get("manufacturer", "Unknown")
                print(f"  - {name} ({manufacturer} {model})")
            
            return sandsara_devices
        else:
            print(f"✗ Failed to get device registry: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error getting devices: {e}")
        return []

if __name__ == "__main__":
    entities = get_sandsara_entities()
    devices = get_devices()
    
    if not entities and not devices:
        print("\n⚠️  No Sandsara entities or devices found.")
        print("The integration may be loaded but not configured yet.")
        print("Try adding the integration via Settings → Devices & Services → Add Integration")