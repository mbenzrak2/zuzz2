#!/usr/bin/env python3
"""
Debug script for ZUZZ TV user management
Run this on server: python3 debug_users.py
"""
import json
import hashlib
import os

DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading data.json: {e}")
        return None

def save_data(d):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print("✅ Data saved successfully")
        return True
    except Exception as e:
        print(f"❌ Error saving data.json: {e}")
        return False

def list_viewers():
    d = load_data()
    if not d:
        return
    
    viewers = d.get('viewers', [])
    print(f"\n📋 Total Viewers: {len(viewers)}")
    print("-" * 60)
    
    for v in viewers:
        print(f"ID: {v['id']}")
        print(f"   Username: {v['username']}")
        print(f"   Email: {v['email']}")
        print(f"   Password Hash: {v['password'][:20]}...")
        print(f"   Created: {v.get('created', 'N/A')}")
        print("-" * 60)

def add_viewer(username, email, password):
    d = load_data()
    if not d:
        return
    
    # Check if exists
    for v in d.get('viewers', []):
        if v['username'].lower() == username.lower():
            print(f"❌ Username '{username}' already exists")
            return
        if v['email'].lower() == email.lower():
            print(f"❌ Email '{email}' already exists")
            return
    
    # Create new viewer
    new_id = max([v['id'] for v in d.get('viewers', [])], default=0) + 1
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    new_viewer = {
        'id': new_id,
        'username': username,
        'email': email,
        'password': hashed,
        'created': '2025-01-01',
        'subscription': None,
        'favorites': []
    }
    
    if 'viewers' not in d:
        d['viewers'] = []
    
    d['viewers'].append(new_viewer)
    
    if save_data(d):
        print(f"✅ Viewer '{username}' added with ID {new_id}")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"   Hash: {hashed[:20]}...")

def test_login(login, password):
    d = load_data()
    if not d:
        return
    
    h = hashlib.sha256(password.encode()).hexdigest()
    print(f"\n🔐 Testing login...")
    print(f"   Login: {login}")
    print(f"   Password: {password}")
    print(f"   Hash: {h[:20]}...")
    
    for v in d.get('viewers', []):
        if v['username'].lower() == login.lower() or v['email'].lower() == login.lower():
            print(f"\n   Found user: {v['username']}")
            print(f"   Stored hash: {v['password'][:20]}...")
            
            if v['password'] == h:
                print("   ✅ PASSWORD MATCH!")
                return True
            else:
                print("   ❌ PASSWORD MISMATCH!")
                print(f"\n   Expected: {v['password']}")
                print(f"   Got:      {h}")
                return False
    
    print("   ❌ User not found")
    return False

def reset_password(login, new_password):
    d = load_data()
    if not d:
        return
    
    for v in d.get('viewers', []):
        if v['username'].lower() == login.lower() or v['email'].lower() == login.lower():
            v['password'] = hashlib.sha256(new_password.encode()).hexdigest()
            if save_data(d):
                print(f"✅ Password reset for '{v['username']}'")
                print(f"   New password: {new_password}")
            return
    
    print(f"❌ User '{login}' not found")

def check_permissions():
    print("\n🔍 Checking file permissions...")
    
    if os.path.exists(DATA_FILE):
        stat = os.stat(DATA_FILE)
        print(f"   data.json exists: ✅")
        print(f"   Size: {stat.st_size} bytes")
        print(f"   Mode: {oct(stat.st_mode)}")
        print(f"   Readable: {'✅' if os.access(DATA_FILE, os.R_OK) else '❌'}")
        print(f"   Writable: {'✅' if os.access(DATA_FILE, os.W_OK) else '❌'}")
    else:
        print(f"   data.json exists: ❌")

if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("   🔧 ZUZZ TV Debug Tool")
    print("=" * 60)
    
    check_permissions()
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python3 debug_users.py list              - List all viewers")
        print("  python3 debug_users.py add USER EMAIL PASS - Add viewer")
        print("  python3 debug_users.py test LOGIN PASS   - Test login")
        print("  python3 debug_users.py reset LOGIN PASS  - Reset password")
        print("\nExample:")
        print("  python3 debug_users.py add ahmed ahmed@test.com mypass123")
        print("  python3 debug_users.py test ahmed mypass123")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == 'list':
        list_viewers()
    elif cmd == 'add' and len(sys.argv) >= 5:
        add_viewer(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'test' and len(sys.argv) >= 4:
        test_login(sys.argv[2], sys.argv[3])
    elif cmd == 'reset' and len(sys.argv) >= 4:
        reset_password(sys.argv[2], sys.argv[3])
    else:
        print("❌ Invalid command")
