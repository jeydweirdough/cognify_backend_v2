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

from services.crud_services import create, read_query, read_one
from database.models import (
    StudentSchema, StudySessionLog, 
    AssessmentSubmission, SubjectSchema
)
from database.enums import (
    BloomTaxonomy, DifficultyLevel, QuestionType, UserRole, PersonalReadinessLevel, ProgressStatus, AssessmentType
)

fake = Faker()

# Configuration
TEST_PREFIX = "test_auto_"
NUM_STUDENTS = 15
NUM_FACULTY = 5
DEFAULT_PASSWORD = "TestPassword123!"
USER_COLLECTION = "user_profiles"

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
        "topics": ["Perspective on Nature and Nurture", "Research Methods", "Developmental Theories", "Developmental Stages"]
    },
    {
        "title": "Abnormal Psychology",
        "description": "Study of psychological disorders, their causes, and treatments.",
        "pqf_level": 6,
        "topics": ["Manifestations of Behavior", "DSM-5 Disorders", "Personality Disorders", "Therapeutic Interventions"]
    },
    {
        "title": "Psychological Assessment",
        "description": "Understanding and using psychological tests.",
        "pqf_level": 6,
        "topics": ["Psychometric Principles", "Validity & Reliability", "Test Administration", "Ethical Standards"]
    },
    {
        "title": "Industrial-Organizational Psychology",
        "description": "Application of psychology to workplace behavior.",
        "pqf_level": 6,
        "topics": ["Organization Theory", "HR Management", "Team Dynamics", "Organizational Change"]
    }
]

def get_utc_now():
    return datetime.now(timezone.utc)

async def create_auth_user(email, role_label):
    try:
        try:
            old_user = auth.get_user_by_email(email)
            auth.delete_user(old_user.uid)
        except:
            pass

        user = auth.create_user(
            email=email,
            password=DEFAULT_PASSWORD,
            display_name=f"{role_label.capitalize()} User",
            email_verified=True
        )
        return user.uid
    except Exception as e:
        print(f"❌ Auth Error for {email}: {e}")
        return None

async def setup_roles():
    print("🔑 Setting up Roles in DB...")
    for key, designation in ROLE_MAP.items():
        role_doc_id = designation
        existing = await read_one("roles", role_doc_id)
        if not existing:
            new_role = {"designation": designation, "created_at": get_utc_now()}
            await create("roles", new_role, doc_id=role_doc_id)
            print(f"   ✅ Created Role: {designation}")
    return ROLE_MAP

async def generate_subjects():
    print("\n📚 Generating Subjects & Curriculum...")
    created_subjects = []
    
    for sub_info in SUBJECT_DATA:
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
                        "id": str(uuid.uuid4()),
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
            "description": sub_info["description"],
            "is_verified": True # Core subjects are auto-verified
        }
        
        res = await create("subjects", subject_data)
        created_subjects.append({"id": res["id"], "data": subject_data})
        print(f"   ✅ Created Subject: {sub_info['title']}")
        
    return created_subjects

async def generate_modules(subjects):
    print("\n📦 Generating Modules...")
    for subj in subjects:
        subj_id = subj['id']
        subj_title = subj['data']['title']
        
        # Create 3 modules per subject
        for i in range(1, 4):
            mod_title = f"{subj_title} - Module {i}"
            existing = await read_query("modules", [("title", "==", mod_title)])
            if existing: 
                continue

            mod_data = {
                "title": mod_title,
                "subject_id": subj_id,
                "purpose": f"Comprehensive learning material for {subj_title} part {i}.",
                "bloom_levels": [random.choice(["Remembering", "Understanding", "Applying"])],
                "material_url": "", 
                "material_type": "pdf",
                "is_verified": True, # Active modules
                "deleted": False,
                "created_at": get_utc_now()
            }
            await create("modules", mod_data)
            print(f"   ✅ Created Module: {mod_title}")

async def generate_subject_assessments(subjects):
    print("\n📝 Generating Subject Assessments...")
    for subj in subjects:
        subj_id = subj['id']
        subj_title = subj['data']['title']
        
        # Create 1 Midterm Exam
        exam_title = f"{subj_title} - Midterm Exam"
        existing = await read_query("assessments", [("title", "==", exam_title)])
        
        if not existing:
            questions = []
            for k in range(5):
                q_id = str(uuid.uuid4())
                questions.append({
                    "id": q_id,
                    "text": f"Question {k+1} for {subj_title}",
                    "type": "multiple_choice",
                    "choices": ["A", "B", "C", "D"],
                    "correct_answers": "A",
                    "bloom_taxonomy": "Applying",
                    "difficulty_level": "Moderate",
                    "competency_id": "temp_comp_id" 
                })

            assess_data = {
                "title": exam_title,
                "subject_id": subj_id,
                "type": "Exam",
                "questions": questions,
                "total_items": len(questions),
                "is_verified": True,
                "is_rejected": False,
                "description": "Midterm evaluation.",
                "created_at": get_utc_now()
            }
            await create("assessments", assess_data)
            print(f"   ✅ Created Assessment: {exam_title}")

async def populate_diagnostic():
    print("\n🚀 Checking Diagnostic Assessment...")
    existing = await read_query("assessments", [("type", "==", "Diagnostic")])
    if existing:
        print("   ℹ️  Diagnostic already exists.")
        return

    print("📦 Creating Diagnostic Assessment Record...")
    questions = []
    for i in range(1, 6):
        q_id = str(uuid.uuid4())
        questions.append({
            "id": q_id,
            "text": f"Diagnostic Question #{i}",
            "type": "multiple_choice",
            "choices": ["A", "B", "C", "D"],
            "correct_answers": "A",
            "competency_id": "general",
            "bloom_taxonomy": "Understanding",
            "difficulty_level": "Moderate"
        })

    assessment_payload = {
        "title": "Initial Diagnostic Assessment",
        "type": AssessmentType.DIAGNOSTIC,
        "subject_id": "general",
        "total_items": 5,
        "questions": questions,
        "is_verified": True,
        "is_rejected": False,
        "created_at": datetime.utcnow(),
        "description": "Standard diagnostic test."
    }
    
    aid = await create("assessments", assessment_payload)
    print(f"   ✅ Diagnostic Assessment Created! ID: {aid['id']}")

# [NEW] GENERATE PENDING (UNVERIFIED) ITEMS FOR ADMIN QUEUE
async def generate_pending_items(subjects):
    print("\n⏳ Generating Pending Verification Items...")
    
    if not subjects:
        print("   ⚠️  No subjects found to attach pending items to.")
        return

    subj = subjects[0] # Attach to first subject for simplicity
    subj_id = subj['id']

    # 1. Pending Module
    pending_mod_title = "Pending: Advanced Cognitive Theory"
    existing_mod = await read_query("modules", [("title", "==", pending_mod_title)])
    if not existing_mod:
        await create("modules", {
            "title": pending_mod_title,
            "subject_id": subj_id,
            "purpose": "Awaiting approval for advanced topics.",
            "bloom_levels": ["Analyzing"],
            "is_verified": False, # <--- IMPORTANT
            "is_rejected": False,
            "deleted": False,
            "created_at": get_utc_now(),
            "created_by": "test_faculty_id" # Mock ID
        })
        print(f"   ⚠️  Created Pending Module: {pending_mod_title}")

    # 2. Pending Assessment
    pending_ass_title = "Pending: Surprise Quiz 1"
    existing_ass = await read_query("assessments", [("title", "==", pending_ass_title)])
    if not existing_ass:
        await create("assessments", {
            "title": pending_ass_title,
            "subject_id": subj_id,
            "type": "Quiz",
            "total_items": 10,
            "is_verified": False, # <--- IMPORTANT
            "is_rejected": False,
            "description": "Draft quiz waiting for review.",
            "created_at": get_utc_now(),
            "created_by": "test_faculty_id"
        })
        print(f"   ⚠️  Created Pending Assessment: {pending_ass_title}")

    # 3. Pending Subject
    pending_sub_title = "Pending: Experimental Psychology"
    existing_sub = await read_query("subjects", [("title", "==", pending_sub_title)])
    if not existing_sub:
        await create("subjects", {
            "title": pending_sub_title,
            "pqf_level": 6,
            "description": "Proposed new elective subject.",
            "is_verified": False, # <--- IMPORTANT
            "is_rejected": False,
            "deleted": False,
            "created_at": get_utc_now(),
            "created_by": "test_faculty_id"
        })
        print(f"   ⚠️  Created Pending Subject: {pending_sub_title}")

async def generate_users(role_ids):
    print("\n👥 Generating Users...")
    
    # 1. Create 1 Admin
    email = f"{TEST_PREFIX}admin@cvsu.edu.ph"
    uid = await create_auth_user(email, "admin")
    if uid:
        user_data = {
            "email": email,
            "first_name": "System",
            "last_name": "Admin",
            "role_id": role_ids["admin"],
            "is_verified": True,
            "is_registered": True,
            "is_active": True,
            "created_at": get_utc_now()
        }
        await create(USER_COLLECTION, user_data, doc_id=uid)
        print(f"   🛡️  Created Admin: {email}")

    # 2. Create Faculty
    for i in range(NUM_FACULTY):
        email = f"{TEST_PREFIX}faculty_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "faculty")
        if uid:
            user_data = {
                "email": email,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "role_id": role_ids["faculty"],
                "is_verified": True,
                "is_registered": True,
                "is_active": True,
                "created_at": get_utc_now()
            }
            await create(USER_COLLECTION, user_data, doc_id=uid)
            print(f"   👨‍🏫 Created Faculty: {email}")

    # 3. Create Students
    student_ids = []
    archetypes = ['high', 'avg', 'low']
    
    for i in range(NUM_STUDENTS):
        email = f"{TEST_PREFIX}student_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "student")
        
        if uid:
            archetype = archetypes[i % 3]
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
                "role_id": role_ids["student"],
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
    print("🚀 STARTING POPULATION")
    print("==================================")
    
    role_ids = await setup_roles()
    subjects = await generate_subjects()
    
    # Generate content
    await generate_modules(subjects)
    await generate_subject_assessments(subjects)
    await populate_diagnostic()
    
    # [NEW] Generate PENDING items for admin verification
    await generate_pending_items(subjects)
    
    student_ids = await generate_users(role_ids)
    await generate_student_data(student_ids, subjects)
    
    print("\n==================================")
    print("✨ POPULATION COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())