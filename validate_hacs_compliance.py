#!/usr/bin/env python3
"""Validate HACS compliance for Sandsara integration"""

import os
import json

def check_file_exists(filepath, description):
    """Check if a required file exists"""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description} MISSING: {filepath}")
        return False

def validate_hacs_json():
    """Validate hacs.json structure"""
    try:
        with open("hacs.json", "r") as f:
            hacs_config = json.load(f)
        
        required_fields = ["name", "homeassistant"]
        optional_fields = ["domain", "content_in_root", "render_readme", "iot_class", "zip_release", "filename"]
        
        print("\n🔍 HACS.json validation:")
        for field in required_fields:
            if field in hacs_config:
                print(f"  ✓ {field}: {hacs_config[field]}")
            else:
                print(f"  ✗ Missing required field: {field}")
        
        for field in optional_fields:
            if field in hacs_config:
                print(f"  + {field}: {hacs_config[field]}")
        
        return True
    except Exception as e:
        print(f"✗ Error validating hacs.json: {e}")
        return False

def validate_manifest():
    """Validate manifest.json structure"""
    try:
        with open("custom_components/sandsara/manifest.json", "r") as f:
            manifest = json.load(f)
        
        required_fields = ["domain", "name", "version", "documentation", "requirements"]
        
        print("\n🔍 Manifest.json validation:")
        for field in required_fields:
            if field in manifest:
                print(f"  ✓ {field}: {manifest[field]}")
            else:
                print(f"  ✗ Missing required field: {field}")
        
        # Check version format
        version = manifest.get("version", "")
        if version and "." in version:
            print(f"  ✓ Version format looks good: {version}")
        else:
            print(f"  ⚠️  Version format might be invalid: {version}")
        
        return True
    except Exception as e:
        print(f"✗ Error validating manifest.json: {e}")
        return False

def check_git_tags():
    """Check if git tags exist"""
    try:
        import subprocess
        result = subprocess.run(["git", "tag", "-l"], capture_output=True, text=True)
        tags = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        print(f"\n🏷️  Git tags: {len(tags)} found")
        for tag in tags:
            if tag:
                print(f"  ✓ {tag}")
        
        if not tags:
            print("  ⚠️  No git tags found - HACS needs version tags for releases")
        
        return len(tags) > 0
    except Exception as e:
        print(f"✗ Error checking git tags: {e}")
        return False

def main():
    print("🔍 HACS Compliance Validation for Sandsara Integration")
    print("=" * 60)
    
    # Check required files
    files_valid = True
    files_valid &= check_file_exists("hacs.json", "HACS configuration")
    files_valid &= check_file_exists("README.md", "README documentation")
    files_valid &= check_file_exists("custom_components/sandsara/manifest.json", "Integration manifest")
    files_valid &= check_file_exists("custom_components/sandsara/__init__.py", "Integration init")
    files_valid &= check_file_exists("CHANGELOG.md", "Changelog (recommended)")
    
    # Check integration structure
    print(f"\n📁 Integration structure:")
    integration_files = [
        "custom_components/sandsara/config_flow.py",
        "custom_components/sandsara/const.py",
        "custom_components/sandsara/coordinator.py",
        "custom_components/sandsara/strings.json",
        "custom_components/sandsara/light.py",
        "custom_components/sandsara/media_player.py",
        "custom_components/sandsara/number.py"
    ]
    
    for filepath in integration_files:
        check_file_exists(filepath, os.path.basename(filepath))
    
    # Validate JSON files
    json_valid = validate_hacs_json() and validate_manifest()
    
    # Check git tags
    tags_valid = check_git_tags()
    
    # Final assessment
    print(f"\n📊 HACS Compliance Summary:")
    print(f"  Files structure: {'✓ PASS' if files_valid else '✗ FAIL'}")
    print(f"  JSON validation: {'✓ PASS' if json_valid else '✗ FAIL'}")
    print(f"  Version tags: {'✓ PASS' if tags_valid else '⚠️  NEEDS ATTENTION'}")
    
    overall_status = files_valid and json_valid and tags_valid
    print(f"\n🎯 Overall HACS compliance: {'✅ READY' if overall_status else '⚠️  NEEDS WORK'}")
    
    if overall_status:
        print(f"\n✨ Integration is ready for HACS!")
        print(f"   Repository URL: https://github.com/monxas/sandsara-hacs")
        print(f"   Add as custom repository in HACS → Integrations")

if __name__ == "__main__":
    main()