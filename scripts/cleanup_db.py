# scripts/cleanup_db.py
import asyncio
import sys
import os
import firebase_admin
from firebase_admin import auth

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.crud_services import read_query, delete
from core.firebase import db

TEST_PREFIX = "test_auto_"
USER_COLLECTION = "user_profiles" # UPDATED

async def cleanup():
    print("🧹 STARTING CLEANUP (DB + AUTH)")
    print("==================================")

    # 1. Find Users in Firestore (user_profiles)
    print(f"🔍 Finding users in {USER_COLLECTION} with prefix: {TEST_PREFIX}...")
    end_prefix = TEST_PREFIX + "\uf8ff"
    
    users = await read_query(USER_COLLECTION, [
        ("email", ">=", TEST_PREFIX),
        ("email", "<", end_prefix)
    ])
    
    if not users:
        print("   ℹ️ No test users found in DB.")
    
    user_ids = [u['id'] for u in users]
    
    # 2. Delete Data in Firestore
    if user_ids:
        print(f"   Found {len(user_ids)} users. Deleting associated data...")
        collections = ["study_logs", "assessment_submissions", "student_progress"]
        
        for col in collections:
            count = 0
            for uid in user_ids:
                docs = await read_query(col, [("user_id", "==", uid)])
                for doc in docs:
                    await delete(col, doc['id'])
                    count += 1
            print(f"   🗑️ Deleted {count} documents from '{col}'")

        # Delete User Docs
        for uid in user_ids:
            await delete(USER_COLLECTION, uid)
        print(f"   🗑️ Deleted {len(user_ids)} documents from {USER_COLLECTION}")

    # 3. Delete Users in Firebase Auth
    print("\n🔐 Cleaning up Firebase Authentication...")
    try:
        if user_ids:
            delete_result = auth.delete_users(user_ids)
            print(f"   ✅ Deleted {delete_result.success_count} users from Auth.")
        else:
            print("   ℹ️ Scanning Auth users for prefix...")
            page = auth.list_users()
            uids_to_delete = []
            for user in page.users:
                if user.email and user.email.startswith(TEST_PREFIX):
                    uids_to_delete.append(user.uid)
            
            if uids_to_delete:
                auth.delete_users(uids_to_delete)
                print(f"   ✅ Deleted {len(uids_to_delete)} users from Auth (Fallback scan).")
                
    except Exception as e:
        print(f"   ❌ Auth Cleanup Error: {e}")

    # 4. Cleanup Subjects
    print("\n📚 Cleaning up Test Subjects...")
    subjects = await read_query("subjects", [])
    del_count = 0
    for sub in subjects:
        desc = sub['data'].get('description', '')
        if desc and desc.startswith(TEST_PREFIX):
            await delete("subjects", sub['id'])
            del_count += 1
    print(f"   🗑️ Deleted {del_count} test subjects")

    print("\n==================================")
    print("✨ SYSTEM CLEANUP COMPLETE")

if __name__ == "__main__":
    asyncio.run(cleanup())