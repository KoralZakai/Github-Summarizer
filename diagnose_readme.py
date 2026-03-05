#!/usr/bin/env python3
"""Diagnose README fetching issue"""

import requests
import base64

def test_readme_endpoints():
    """Test different README endpoints"""
    owner, repo = "pallets", "flask"
    
    endpoints = [
        f"https://api.github.com/repos/{owner}/{repo}/readme",
        f"https://api.github.com/repos/{owner}/{repo}/contents/README.md",
        f"https://api.github.com/repos/{owner}/{repo}/contents/README.rst",
        f"https://api.github.com/repos/{owner}/{repo}/contents/README",
    ]
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    for endpoint in endpoints:
        print(f"\n{'='*70}")
        print(f"Testing: {endpoint.split('/')[-1]}")
        print('='*70)
        
        try:
            res = requests.get(endpoint, headers=headers, timeout=5)
            print(f"Status: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                print(f"Response keys: {data.keys()}")
                
                if "content" in data:
                    content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
                    print(f"Content length: {len(content)} chars")
                    print(f"First 200 chars:\n{content[:200]}")
                else:
                    print(f"Content: {str(data)[:200]}")
            else:
                print(f"Response: {res.text[:200]}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_readme_endpoints()
