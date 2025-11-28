# scripts/cleanup_db.py
import asyncio
import sys
import os
import firebase_admin
from firebase_admin import auth

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [FIX] Added read_one to imports
from services.crud_services import read_query, delete, read_one
from core.firebase import db

# Configuration matching populate_db.py
TEST_PREFIX = "test_auto_"
USER_COLLECTION = "user_profiles"

# Subjects created by populate_db.py (Exact Titles)
TARGET_SUBJECTS = [
    "Developmental Psychology",
    "Abnormal Psychology",
    "Psychological Assessment",
    "Industrial-Organizational Psychology"
]

# Roles created by populate_db.py (Fixed IDs)
TARGET_ROLES = ["admin", "student", "faculty_member"]

async def cleanup():
    print("🧹 STARTING SYSTEM CLEANUP")
    print("==================================")

    # 1. Find Test Users
    print(f"🔍 Finding users in '{USER_COLLECTION}' with prefix: '{TEST_PREFIX}'...")
    end_prefix = TEST_PREFIX + "\uf8ff"
    
    users = await read_query(USER_COLLECTION, [
        ("email", ">=", TEST_PREFIX),
        ("email", "<", end_prefix)
    ])
    
    user_ids = [u['id'] for u in users]
    
    if not user_ids:
        print("   ℹ️  No test users found in DB.")
    else:
        print(f"   Found {len(user_ids)} users. Deleting associated data...")

        # 2. Delete Related Data (Logs, Assessments)
        # We query these collections for any docs linked to the users we are deleting
        related_collections = ["study_logs", "assessment_submissions"] 
        
        for col in related_collections:
            total_deleted = 0
            for uid in user_ids:
                # Find docs belonging to this user
                docs = await read_query(col, [("user_id", "==", uid)])
                for doc in docs:
                    await delete(col, doc['id'])
                    total_deleted += 1
            
            if total_deleted > 0:
                print(f"   🗑️  Deleted {total_deleted} items from '{col}'")

        # 3. Delete User Profiles
        for uid in user_ids:
            await delete(USER_COLLECTION, uid)
        print(f"   🗑️  Deleted {len(user_ids)} profiles from '{USER_COLLECTION}'")

    # 4. Cleanup Firebase Auth
    print("\n🔐 Cleaning up Firebase Authentication...")
    
    # Method A: Delete by DB IDs (Fastest)
    if user_ids:
        try:
            result = auth.delete_users(user_ids)
            print(f"   ✅ Deleted {result.success_count} users by ID match.")
            if result.failure_count > 0:
                print(f"   ⚠️  Failed to delete {result.failure_count} users.")
        except Exception as e:
            print(f"   ❌ Auth Delete Error: {e}")

    # Method B: Fallback Scan (Catches orphaned Auth users that might not be in DB)
    try:
        print("   ℹ️  Scanning for orphaned Auth users...")
        page = auth.list_users()
        orphaned_uids = []
        for user in page.users:
            if user.email and user.email.startswith(TEST_PREFIX):
                if user.uid not in user_ids: # Only delete if not already deleted above
                    orphaned_uids.append(user.uid)
        
        if orphaned_uids:
            auth.delete_users(orphaned_uids)
            print(f"   ✅ Deleted {len(orphaned_uids)} orphaned users.")
            
    except Exception as e:
        print(f"   ❌ Auth Scan Error: {e}")

    # 5. Cleanup Subjects
    print("\n📚 Cleaning up Subjects...")
    deleted_subjects = 0
    for title in TARGET_SUBJECTS:
        # Find subject by title
        matches = await read_query("subjects", [("title", "==", title)])
        for sub in matches:
            await delete("subjects", sub['id'])
            deleted_subjects += 1
            
    print(f"   🗑️  Deleted {deleted_subjects} subjects.")

    # 6. Cleanup Roles
    print("\n🔑 Cleaning up Roles...")
    deleted_roles = 0
    for role_id in TARGET_ROLES:
        try:
            # Check if role exists before trying to delete
            role = await read_one("roles", role_id)
            if role:
                await delete("roles", role_id)
                deleted_roles += 1
        except Exception as e:
            print(f"   ⚠️ Error deleting role {role_id}: {e}")
            
    print(f"   🗑️  Deleted {deleted_roles} roles.")

    print("\n==================================")
    print("✨ CLEANUP COMPLETE")

if __name__ == "__main__":
    asyncio.run(cleanup())