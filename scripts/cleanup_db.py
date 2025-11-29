# scripts/cleanup_db.py
import asyncio
import sys
import os
import firebase_admin
from firebase_admin import auth

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.crud_services import read_query, delete, read_one
from core.firebase import db

# Configuration matching populate_db.py
TEST_PREFIX = "test_auto_"
USER_COLLECTION = "user_profiles"

TARGET_SUBJECTS = [
    "Developmental Psychology",
    "Abnormal Psychology",
    "Psychological Assessment",
    "Industrial-Organizational Psychology"
]

TARGET_ROLES = ["admin", "student", "faculty_member"]

async def cleanup():
    print("🧹 STARTING SYSTEM CLEANUP")
    print("==================================")

    # 1. Users & Auth
    print(f"🔍 Finding users with prefix: '{TEST_PREFIX}'...")
    end_prefix = TEST_PREFIX + "\uf8ff"
    users = await read_query(USER_COLLECTION, [("email", ">=", TEST_PREFIX), ("email", "<", end_prefix)])
    user_ids = [u['id'] for u in users]
    
    if user_ids:
        print(f"   Found {len(user_ids)} users. Deleting associated data...")
        related_collections = ["study_logs", "assessment_submissions"]
        for col in related_collections:
            total_deleted = 0
            for uid in user_ids:
                docs = await read_query(col, [("user_id", "==", uid)])
                for doc in docs:
                    await delete(col, doc['id'])
                    total_deleted += 1
            if total_deleted > 0: print(f"   🗑️  Deleted {total_deleted} items from '{col}'")

        for uid in user_ids: await delete(USER_COLLECTION, uid)
        print(f"   🗑️  Deleted {len(user_ids)} profiles.")
        
        try:
            auth.delete_users(user_ids)
            print(f"   ✅ Deleted {len(user_ids)} Auth users.")
        except Exception as e:
            print(f"   ❌ Auth Delete Error: {e}")

    # 2. Subjects, Modules, Assessments
    print("\n📚 Cleaning up Curriculum Data...")
    deleted_subjects = 0
    deleted_modules = 0
    deleted_assessments = 0

    for title in TARGET_SUBJECTS:
        # Find subject by title
        matches = await read_query("subjects", [("title", "==", title)])
        for sub in matches:
            sid = sub['id']
            
            # Delete Modules linked to this subject
            modules = await read_query("modules", [("subject_id", "==", sid)])
            for mod in modules:
                await delete("modules", mod['id'])
                deleted_modules += 1

            # Delete Assessments linked to this subject
            assessments = await read_query("assessments", [("subject_id", "==", sid)])
            for ass in assessments:
                await delete("assessments", ass['id'])
                deleted_assessments += 1

            # Delete Subject itself
            await delete("subjects", sid)
            deleted_subjects += 1
            
    # Cleanup Diagnostic (Subject ID = 'general')
    diagnostics = await read_query("assessments", [("subject_id", "==", "general")])
    for diag in diagnostics:
        await delete("assessments", diag['id'])
        deleted_assessments += 1

    print(f"   🗑️  Deleted {deleted_subjects} subjects.")
    print(f"   🗑️  Deleted {deleted_modules} modules.")
    print(f"   🗑️  Deleted {deleted_assessments} assessments.")

    print("\n==================================")
    print("✨ CLEANUP COMPLETE")

if __name__ == "__main__":
    asyncio.run(cleanup())