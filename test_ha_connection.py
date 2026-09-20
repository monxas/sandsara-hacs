#!/usr/bin/env python3
"""Test Home Assistant API connection"""

import os
import requests
import json

HA_URL = "http://192.168.0.171:8123"
HA_TOKEN = os.environ.get("HASS_TOKEN") or exit("falta HASS_TOKEN en el entorno")

headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "content-type": "application/json",
}

def test_connection():
    """Test basic connection to HA API"""
    try:
        response = requests.get(f"{HA_URL}/api/", headers=headers)
        if response.status_code == 200:
            print("✓ Home Assistant API connection successful")
            print(f"HA Version: {response.json().get('version')}")
            return True
        else:
            print(f"✗ API connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def check_integrations():
    """Check if custom integrations are loaded"""
    try:
        response = requests.get(f"{HA_URL}/api/config", headers=headers)
        if response.status_code == 200:
            config = response.json()
            components = config.get("components", [])
            print(f"✓ Total components loaded: {len(components)}")
            
            # Check for our integration
            if "sandsara" in components:
                print("✓ Sandsara integration is already loaded!")
            else:
                print("- Sandsara integration not currently loaded")
            
            return True
        else:
            print(f"✗ Config check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Config check error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Home Assistant connection...")
    if test_connection():
        check_integrations()