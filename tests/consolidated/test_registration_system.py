#!/usr/bin/env python3
"""
Test script for the user registration and subscription system.
"""

import asyncio
import httpx
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

async def test_registration_system():
    """Test the complete registration and subscription system."""
    
    print("🧪 Testing User Registration & Subscription System")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        # Test 1: Get available packages
        print("\n1️⃣ Testing package retrieval...")
        try:
            response = await client.get(f"{BASE_URL}/api/packages")
            if response.status_code == 200:
                packages = response.json()
                print(f"✅ Found {len(packages)} packages:")
                for pkg in packages:
                    print(f"   - {pkg['name']}: ${pkg['price_monthly']}/month")
            else:
                print(f"❌ Failed to get packages: {response.status_code}")
        except Exception as e:
            print(f"❌ Error getting packages: {e}")
        
        # Test 2: Register a new user
        print("\n2️⃣ Testing user registration...")
        registration_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "company_name": "Test Company",
            "phone": "+1234567890",
            "package_type": "free",
            "billing_cycle": "monthly"
        }
        
        try:
            response = await client.post(f"{BASE_URL}/api/register", json=registration_data)
            if response.status_code == 200:
                result = response.json()
                print("✅ User registered successfully!")
                print(f"   - User ID: {result['user_id']}")
                print(f"   - Email: {result['email']}")
                print(f"   - Full Name: {result['full_name']}")
                print(f"   - Package: {result['subscription']['package']['name']}")
                print(f"   - Status: {result['subscription']['status']}")
                
                # Store token for further tests
                access_token = result['access_token']
                user_id = result['user_id']
                
            else:
                print(f"❌ Registration failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return
                
        except Exception as e:
            print(f"❌ Error during registration: {e}")
            return
        
        # Test 3: Get user subscription
        print("\n3️⃣ Testing subscription retrieval...")
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(f"{BASE_URL}/api/subscription", headers=headers)
            if response.status_code == 200:
                subscription = response.json()
                print("✅ Subscription retrieved successfully!")
                print(f"   - Package: {subscription['package']['name']}")
                print(f"   - Status: {subscription['status']}")
                print(f"   - Billing Cycle: {subscription['billing_cycle']}")
                print(f"   - Messages Used: {subscription['messages_used_this_month']}")
            else:
                print(f"❌ Failed to get subscription: {response.status_code}")
        except Exception as e:
            print(f"❌ Error getting subscription: {e}")
        
        # Test 4: Get usage stats
        print("\n4️⃣ Testing usage stats...")
        try:
            response = await client.get(f"{BASE_URL}/api/usage", headers=headers)
            if response.status_code == 200:
                usage = response.json()
                print("✅ Usage stats retrieved successfully!")
                print(f"   - Messages: {usage['messages_used_this_month']}/{usage['messages_limit']} ({usage['messages_usage_percent']:.1f}%)")
                print(f"   - Customers: {usage['customers_created']}/{usage['customers_limit']} ({usage['customers_usage_percent']:.1f}%)")
                print(f"   - Storage: {usage['storage_used_gb']:.1f}GB/{usage['storage_limit_gb']}GB ({usage['storage_usage_percent']:.1f}%)")
                print(f"   - Near Limit: {usage['is_near_limit']}")
                print(f"   - Over Limit: {usage['is_over_limit']}")
            else:
                print(f"❌ Failed to get usage stats: {response.status_code}")
        except Exception as e:
            print(f"❌ Error getting usage stats: {e}")
        
        # Test 5: Test subscription upgrade (simulation)
        print("\n5️⃣ Testing subscription upgrade...")
        try:
            upgrade_data = {
                "package_type": "plus",
                "billing_cycle": "monthly"
            }
            response = await client.post(f"{BASE_URL}/api/subscription/upgrade", json=upgrade_data, headers=headers)
            if response.status_code == 200:
                upgrade_result = response.json()
                print("✅ Upgrade request processed!")
                print(f"   - Success: {upgrade_result['success']}")
                print(f"   - Message: {upgrade_result['message']}")
                print(f"   - Payment Required: {upgrade_result['payment_required']}")
                if upgrade_result['payment_required']:
                    print(f"   - Payment URL: {upgrade_result['payment_url']}")
            else:
                print(f"❌ Upgrade failed: {response.status_code}")
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"❌ Error during upgrade: {e}")
        
        # Test 6: Test package by type
        print("\n6️⃣ Testing package by type...")
        try:
            response = await client.get(f"{BASE_URL}/api/packages/pro")
            if response.status_code == 200:
                package = response.json()
                print("✅ Pro package retrieved successfully!")
                print(f"   - Name: {package['name']}")
                print(f"   - Price: ${package['price_monthly']}/month")
                print(f"   - Features: {package['has_analytics']}, {package['has_priority_support']}")
            else:
                print(f"❌ Failed to get pro package: {response.status_code}")
        except Exception as e:
            print(f"❌ Error getting pro package: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 Registration system test completed!")
        print("\nTo test the frontend:")
        print("1. Start the backend: make dev")
        print("2. Start the frontend: cd web && npm run dev")
        print("3. Visit: http://localhost:3000/register")

if __name__ == "__main__":
    asyncio.run(test_registration_system())