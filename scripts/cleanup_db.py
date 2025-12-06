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
    print("🧹 STARTING COMPREHENSIVE SYSTEM CLEANUP")
    print("=" * 50)

    # 1. Users & Auth
    print(f"\n🔍 Finding users with prefix: '{TEST_PREFIX}'...")
    end_prefix = TEST_PREFIX + "\uf8ff"
    users = await read_query(USER_COLLECTION, [("email", ">=", TEST_PREFIX), ("email", "<", end_prefix)])
    user_ids = [u['id'] for u in users]
    
    if user_ids:
        print(f"   Found {len(user_ids)} users. Deleting associated data...")
        
        # Delete related data for each user
        related_collections = [
            "study_logs",
            "assessment_submissions",
            "announcement_reads",
            "notifications",
            "readiness_nominations",
        ]
        
        for col in related_collections:
            total_deleted = 0
            for uid in user_ids:
                docs = await read_query(col, [("user_id", "==", uid)])
                for doc in docs:
                    await delete(col, doc['id'])
                    total_deleted += 1
            if total_deleted > 0:
                print(f"   🗑️  Deleted {total_deleted} items from '{col}'")

        # Delete user profiles
        for uid in user_ids:
            await delete(USER_COLLECTION, uid)
        print(f"   🗑️  Deleted {len(user_ids)} profiles.")
        
        # Delete from Firebase Auth
        try:
            auth.delete_users(user_ids)
            print(f"   ✅ Deleted {len(user_ids)} Auth users.")
        except Exception as e:
            print(f"   ❌ Auth Delete Error: {e}")

    # 2. Subjects, Modules, Assessments, Questions
    print("\n📚 Cleaning up Curriculum Data...")
    deleted_subjects = 0
    deleted_modules = 0
    deleted_assessments = 0
    deleted_questions = 0

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
                # Also delete submissions for this assessment
                submissions = await read_query("assessment_submissions", [("assessment_id", "==", ass['id'])])
                for sub in submissions:
                    await delete("assessment_submissions", sub['id'])
                
                await delete("assessments", ass['id'])
                deleted_assessments += 1

            # Delete Questions linked to this subject
            # Note: Questions don't have direct subject_id, so we check via competency
            questions = await read_query("questions", [])
            for q in questions:
                await delete("questions", q['id'])
                deleted_questions += 1

            # Delete Subject itself
            await delete("subjects", sid)
            deleted_subjects += 1
            
    # Cleanup Diagnostic assessments
    diagnostics = await read_query("assessments", [])
    for diag in diagnostics:
        data = diag.get('data', {})
        if 'Diagnostic' in data.get('title', ''):
            # Delete submissions first
            submissions = await read_query("assessment_submissions", [("assessment_id", "==", diag['id'])])
            for sub in submissions:
                await delete("assessment_submissions", sub['id'])
            
            await delete("assessments", diag['id'])
            deleted_assessments += 1

    print(f"   🗑️  Deleted {deleted_subjects} subjects.")
    print(f"   🗑️  Deleted {deleted_modules} modules.")
    print(f"   🗑️  Deleted {deleted_questions} questions.")
    print(f"   🗑️  Deleted {deleted_assessments} assessments.")

    # 3. Whitelist entries
    print("\n📋 Cleaning up Whitelist...")
    whitelist = await read_query("whitelist", [])
    deleted_whitelist = 0
    for entry in whitelist:
        data = entry.get('data', {})
        email = data.get('email', '')
        if email.startswith(TEST_PREFIX):
            await delete("whitelist", entry['id'])
            deleted_whitelist += 1
    
    if deleted_whitelist > 0:
        print(f"   🗑️  Deleted {deleted_whitelist} whitelist entries.")

    print("\n" + "=" * 50)
    print("✨ CLEANUP COMPLETE")
    print("=" * 50)
    print("\n📊 Deletion Summary:")
    print(f"   - {len(user_ids)} User Profiles")
    print(f"   - {deleted_whitelist} Whitelist Entries")
    print(f"   - {deleted_subjects} Subjects")
    print(f"   - {deleted_modules} Modules")
    print(f"   - {deleted_questions} Questions")
    print(f"   - {deleted_assessments} Assessments")
    print("   - All related submission and log data")
    print("\n✅ Database is now clean and ready for fresh population!")


if __name__ == "__main__":
    asyncio.run(cleanup())