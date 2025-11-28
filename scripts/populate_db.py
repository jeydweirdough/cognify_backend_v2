# scripts/populate_db.py
import asyncio
import sys
import os
import random
import uuid
from datetime import datetime, timezone
from faker import Faker
import firebase_admin
from firebase_admin import auth

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [FIX] Added read_one to imports
from services.crud_services import create, read_query, read_one
from database.models import (
    StudentSchema, StudySessionLog, 
    AssessmentSubmission, SubjectSchema
)
from database.enums import (
    UserRole, PersonalReadinessLevel, ProgressStatus, AssessmentType
)

fake = Faker()

# Configuration
TEST_PREFIX = "test_auto_"
NUM_STUDENTS = 15
NUM_FACULTY = 5
DEFAULT_PASSWORD = "TestPassword123!"
USER_COLLECTION = "user_profiles"

# [FIX] Role Map with Fixed IDs
# Key = Internal Reference, Value = Firestore Document ID & Designation
ROLE_MAP = {
    "admin": "admin",
    "student": "student",
    "faculty": "faculty_member"
}

# PQF Level 6 Subjects (Psychology)
SUBJECT_DATA = [
    {
        "title": "Developmental Psychology",
        "description": "Study of human growth and changes from childhood to adulthood.",
        "pqf_level": 6,
        "topics": ["Perspective on Nature and Nurture", "Research Methods in Developmental Psychology & Ethical Considerations", "Developmental Theories", "Developmental Principles", "Developmental Issues", "Developmental Challenges and Milestones on Developmental Stages"]
    },
    {
        "title": "Abnormal Psychology",
        "description": "Study of psychological disorders, their causes, and treatments.",
        "pqf_level": 6,
        "topics": ["Manifestations of Behavior", " Psychological Disorders and Specific Symptoms based on DSM-5", "Personality Disorders", "Theoritical Approaches in Explaining the Etiology of Psychological Disorders", "Therapeutic Intervention of Psychological Disorders", "Socio-Cultural Factors & Ethical Principles in Diagnosing Abnormal Behavior", "Global Health Crisis & Mental Health Law"]
    },
    {
        "title": "Psychological Assessment",
        "description": "Understanding and using psychological tests to measure behavior and mental processes.",
        "pqf_level": 6,
        "topics": ["Psychometric Properties & Principles", "Research Methods & Statistics", "Validity & Reliability", "Selection of Assessment Methods & Tools", "Test Administration & Scoring", "Ethical Principles & Standards of Practice"]
    },
    {
        "title": "Industrial-Organizational Psychology",
        "description": "Application of psychology to workplace behavior and performance.",
        "pqf_level": 6,
        "topics": ["Organization Theory", "Human Resource Management", "Team Dynamics", "Organizational Change & Development"]
    }
]

def get_utc_now():
    return datetime.now(timezone.utc)

async def create_auth_user(email, role_label):
    """Creates user in Firebase Auth and returns UID."""
    try:
        # Delete if exists to ensure clean state
        try:
            old_user = auth.get_user_by_email(email)
            auth.delete_user(old_user.uid)
            print(f"   ♻️  Recreating Auth: {email}")
        except:
            pass

        user = auth.create_user(
            email=email,
            password=DEFAULT_PASSWORD,
            display_name=f"{role_label.capitalize()} User",
            email_verified=True # Auto-verify for testing
        )
        return user.uid
    except Exception as e:
        print(f"❌ Auth Error for {email}: {e}")
        return None

async def setup_roles():
    """
    Creates 'roles' collection with FIXED Document IDs.
    This ensures 'roles/student' always exists with ID 'student'.
    """
    print("🔑 Setting up Roles in DB...")
    
    for key, designation in ROLE_MAP.items():
        role_doc_id = designation # Use designation as the ID (e.g. 'admin')
        
        # Check if role exists by ID
        existing = await read_one("roles", role_doc_id)
        
        if existing:
            print(f"   ℹ️  Role exists: {designation}")
        else:
            # Create it with matching ID and designation
            new_role = {
                "designation": designation, 
                "created_at": get_utc_now()
            }
            await create("roles", new_role, doc_id=role_doc_id)
            print(f"   ✅ Created Role: {designation} (ID: {role_doc_id})")
    
    return ROLE_MAP

async def generate_subjects():
    """Creates subjects, topics, and competencies."""
    print("\n📚 Generating Subjects & Curriculum...")
    created_subjects = []
    
    for sub_info in SUBJECT_DATA:
        # Check duplicates
        existing = await read_query("subjects", [("title", "==", sub_info["title"])])
        if existing:
            created_subjects.append(existing[0])
            continue

        topics = []
        for topic_title in sub_info["topics"]:
            topics.append({
                "id": str(uuid.uuid4()),
                "title": topic_title,
                "weight_percentage": 25.0,
                "competencies": [
                    {
                        "code": f"1.{i}",
                        "description": f"Competency {i} for {topic_title}",
                        "target_bloom_level": "understanding",
                        "target_difficulty": "Moderate",
                        "allocated_items": 5
                    } for i in range(1, 4)
                ]
            })

        subject_data = {
            "title": sub_info["title"],
            "pqf_level": sub_info["pqf_level"],
            "total_weight_percentage": 100.0,
            "topics": topics,
            "created_at": get_utc_now(),
            "description": sub_info["description"]
        }
        
        res = await create("subjects", subject_data)
        created_subjects.append({"id": res["id"], "data": subject_data})
        print(f"   ✅ Created Subject: {sub_info['title']}")
        
    return created_subjects

async def generate_users(role_ids):
    """Creates Admin, Faculty, and Student users."""
    print("\n👥 Generating Users...")
    
    # 1. Create 1 Admin
    email = f"{TEST_PREFIX}admin@cvsu.edu.ph"
    uid = await create_auth_user(email, "admin")
    if uid:
        user_data = {
            "email": email,
            "first_name": "System",
            "last_name": "Admin",
            "role_id": role_ids["admin"],  # ID will be "admin"
            "is_verified": True,
            "is_registered": True,
            "is_active": True,
            "created_at": get_utc_now()
        }
        await create(USER_COLLECTION, user_data, doc_id=uid)
        print(f"   🛡️  Created Admin: {email}")

    # 2. Create 5 Faculty Members
    for i in range(NUM_FACULTY):
        email = f"{TEST_PREFIX}faculty_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "faculty")
        
        if uid:
            user_data = {
                "email": email,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "role_id": role_ids["faculty"], # ID will be "faculty_member"
                "is_verified": True,
                "is_registered": True,
                "is_active": True,
                "created_at": get_utc_now()
            }
            await create(USER_COLLECTION, user_data, doc_id=uid)
            print(f"   👨‍🏫 Created Faculty: {email}")

    # 3. Create 15 Students
    student_ids = []
    archetypes = ['high', 'avg', 'low']
    
    for i in range(NUM_STUDENTS):
        email = f"{TEST_PREFIX}student_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "student")
        
        if uid:
            archetype = archetypes[i % 3]
            # [Logic for archetypes same as before...]
            if archetype == 'high':
                readiness = PersonalReadinessLevel.HIGH
                avg_sess = random.uniform(45, 90)
                pace = "Fast"
                intr = "Low"
            elif archetype == 'low':
                readiness = PersonalReadinessLevel.LOW
                avg_sess = random.uniform(10, 25)
                pace = "Slow"
                intr = "High"
            else:
                readiness = PersonalReadinessLevel.MODERATE
                avg_sess = random.uniform(25, 45)
                pace = "Standard"
                intr = "Medium"

            behavior_profile_data = {
                "average_session_length": avg_sess,
                "preferred_study_time": random.choice(["Morning", "Evening"]),
                "interruption_frequency": intr,
                "learning_pace": pace,
                "reading_pattern": "continuous",
                "assessment_pace": "moderate",
                "focus_level": "Medium",
                "last_updated": get_utc_now()
            }

            student_info = StudentSchema(
                user_id=uid,
                personal_readiness=readiness,
                timeliness=random.randint(50, 100),
                confident_subject=[],
                behavior_profile=behavior_profile_data
            )

            user_data = {
                "email": email,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "role_id": role_ids["student"], # ID will be "student"
                "is_verified": True,
                "is_registered": True,
                "is_active": True,
                "student_info": student_info.model_dump(),
                "created_at": get_utc_now()
            }
            
            await create(USER_COLLECTION, user_data, doc_id=uid)
            student_ids.append(uid)
            print(f"   🎓 Created Student: {email} ({archetype})")
            
    return student_ids

async def generate_student_data(student_ids, subjects):
    """Generates Logs and Assessments linked to students."""
    print("\n📊 Generating Student Activity...")
    
    for uid in student_ids:
        # Study Logs
        for _ in range(random.randint(5, 10)):
            subj = random.choice(subjects)
            log = StudySessionLog(
                user_id=uid,
                resource_id=subj['id'],
                resource_type="module",
                start_time=fake.date_time_between(start_date='-30d', end_date='now'),
                duration_seconds=random.randint(300, 3600),
                interruptions_count=random.randint(0, 5),
                idle_time_seconds=random.randint(0, 300),
                completion_status=ProgressStatus.COMPLETED
            )
            await create("study_logs", log.model_dump())

        # Assessment Submissions
        for _ in range(random.randint(2, 5)):
            subj = random.choice(subjects)
            sub = AssessmentSubmission(
                user_id=uid,
                assessment_id=str(uuid.uuid4()),
                subject_id=subj['id'],
                answers=[], 
                score=random.uniform(40, 100),
                total_items=20,
                time_taken_seconds=random.randint(600, 2000),
                submitted_at=fake.date_time_between(start_date='-30d', end_date='now')
            )
            await create("assessment_submissions", sub.model_dump())
            
    print(f"   ✅ Generated activity for {len(student_ids)} students")

async def main():
    print("🚀 STARTING POPULATION (FIXED ROLES)")
    print("==================================")
    
    role_ids = await setup_roles()
    subjects = await generate_subjects()
    student_ids = await generate_users(role_ids)
    await generate_student_data(student_ids, subjects)
    
    print("\n==================================")
    print("✨ POPULATION COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())