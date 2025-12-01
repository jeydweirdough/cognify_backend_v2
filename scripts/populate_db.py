# scripts/populate_db.py
import asyncio
import sys
import os
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker
import firebase_admin
from firebase_admin import auth

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Initialize Firebase
from core.firebase import db 
from services.crud_services import create, read_query, read_one, delete
from database.enums import (
    BloomTaxonomy, DifficultyLevel, QuestionType, UserRole, 
    PersonalReadinessLevel, ProgressStatus, AssessmentType
)

fake = Faker()

# --- CONFIGURATION ---
TEST_PREFIX = "test_auto_"
NUM_STUDENTS = 25 
NUM_FACULTY = 3
DEFAULT_PASSWORD = "TestPassword123!"
USER_COLLECTION = "user_profiles"
WHITELIST_COLLECTION = "whitelist"

# --- DATA DEFINITIONS ---

ROLE_MAP = {
    "admin": "admin",
    "student": "student",
    "faculty": "faculty_member"
}

# Curriculum Data (Subject -> Topics -> Competencies)
SUBJECT_DATA = [
    {
        "title": "Developmental Psychology",
        "description": "Study of human growth and changes from childhood to adulthood.",
        "pqf_level": 6,
        "topics": [
            {"title": "Nature vs Nurture", "comps": ["Analyze genetic influences", "Evaluate environmental factors"]},
            {"title": "Research Methods", "comps": ["Compare longitudinal vs cross-sectional", "Design developmental studies"]},
            {"title": "Piaget's Stages", "comps": ["Differentiate sensorimotor and preoperational", "Apply concrete operational concepts"]}
        ]
    },
    {
        "title": "Abnormal Psychology",
        "description": "Study of psychological disorders, their causes, and treatments.",
        "pqf_level": 6,
        "topics": [
            {"title": "Anxiety Disorders", "comps": ["Identify symptoms of GAD", "Differentiate phobias"]},
            {"title": "DSM-5 Criteria", "comps": ["Apply diagnostic criteria", "Evaluate comorbidity"]},
            {"title": "Personality Disorders", "comps": ["Analyze Cluster B traits", "Critique treatment approaches"]}
        ]
    },
    {
        "title": "Psychological Assessment",
        "description": "Understanding and using psychological tests.",
        "pqf_level": 6,
        "topics": [
            {"title": "Psychometrics", "comps": ["Calculate standard deviation", "Interpret normal distribution"]},
            {"title": "Validity & Reliability", "comps": ["Differentiate content and construct validity", "Assess test-retest reliability"]},
            {"title": "IQ Testing", "comps": ["Interpret WAIS-IV scores", "Analyze cultural bias in testing"]}
        ]
    }
]

def get_utc_now():
    return datetime.now(timezone.utc)

async def create_auth_user(email, role_label):
    """Creates user in Firebase Auth and returns UID."""
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
        print(f"   ⚠️ Auth Error ({email}): {e}")
        # If auth fails (e.g. password policy), we skip DB creation for this user
        return None

async def setup_roles():
    print("🔑 Setting up Roles...")
    for key, designation in ROLE_MAP.items():
        role_doc_id = designation 
        existing = await read_one("roles", role_doc_id)
        if not existing:
            new_role = {"designation": designation, "created_at": get_utc_now()}
            await create("roles", new_role, doc_id=role_doc_id)
    return ROLE_MAP

async def create_whitelist_entry(email, role, adder_id="system"):
    """Adds email to whitelist so they can pass the SignUp check."""
    # Check if exists
    existing = await read_query(WHITELIST_COLLECTION, [("email", "==", email)])
    if existing:
        return existing[0]['id']
        
    entry = {
        "email": email,
        "assigned_role": role,
        "is_registered": True, # Auto-mark as registered since we are seeding
        "added_by": adder_id,
        "created_at": get_utc_now()
    }
    res = await create(WHITELIST_COLLECTION, entry)
    return res['id']

async def generate_users(role_ids):
    print("\n👥 Generating Users & Whitelist...")
    faculty_ids = []
    student_ids = []
    
    # 1. Admin
    admin_email = f"{TEST_PREFIX}admin@cvsu.edu.ph"
    uid = await create_auth_user(admin_email, "admin")
    if uid:
        await create(USER_COLLECTION, {
            "email": admin_email,
            "first_name": "System", "last_name": "Admin", "user_name": "sysadmin",
            "role_id": role_ids["admin"], "is_verified": True, "is_registered": True, "is_active": True,
            "created_at": get_utc_now()
        }, doc_id=uid)
        await create_whitelist_entry(admin_email, UserRole.ADMIN, uid)

    # 2. Faculty
    for i in range(NUM_FACULTY):
        email = f"{TEST_PREFIX}faculty_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "faculty")
        if uid:
            await create(USER_COLLECTION, {
                "email": email, "first_name": fake.first_name(), "last_name": fake.last_name(),
                "user_name": f"faculty_{i}",
                "role_id": role_ids["faculty"], "is_verified": True, "is_registered": True, "is_active": True,
                "created_at": get_utc_now()
            }, doc_id=uid)
            faculty_ids.append(uid)
            await create_whitelist_entry(email, UserRole.FACULTY, "system")

    # 3. Students
    for i in range(NUM_STUDENTS):
        email = f"{TEST_PREFIX}student_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "student")
        if uid:
            student_info = {
                "user_id": uid,
                "personal_readiness": random.choice(list(PersonalReadinessLevel)),
                "timeliness": random.randint(60, 100),
                "confident_subject": [],
                "behavior_profile": {
                    "learning_pace": "Standard",
                    "interruption_frequency": "Low"
                },
                "progress_report": []
            }
            await create(USER_COLLECTION, {
                "email": email, "first_name": fake.first_name(), "last_name": fake.last_name(),
                "user_name": f"student_{i}",
                "role_id": role_ids["student"], "is_verified": True, "is_registered": True, "is_active": True,
                "student_info": student_info,
                "created_at": get_utc_now()
            }, doc_id=uid)
            student_ids.append(uid)
            await create_whitelist_entry(email, UserRole.STUDENT, "system")
            
    print(f"   ✅ Created: {len(student_ids)} Students, {len(faculty_ids)} Faculty, 1 Admin")
    return student_ids, faculty_ids

async def generate_content(student_ids, faculty_ids):
    print("\n📚 Generating Content (Subjects, Modules, Assessments)...")
    
    created_subjects = []
    total_modules = 0
    total_assessments = 0

    for sub_info in SUBJECT_DATA:
        # 1. Create Subject
        topics = []
        all_comps_in_subject = [] # To link assessments later

        for topic_data in sub_info["topics"]:
            competencies = []
            for comp_text in topic_data["comps"]:
                comp_id = str(uuid.uuid4())
                competency = {
                    "id": comp_id,
                    "code": f"C-{random.randint(100,999)}",
                    "description": comp_text,
                    "target_bloom_level": random.choice(list(BloomTaxonomy)),
                    "target_difficulty": random.choice(list(DifficultyLevel)),
                    "allocated_items": 5
                }
                competencies.append(competency)
                all_comps_in_subject.append(competency)

            topics.append({
                "id": str(uuid.uuid4()),
                "title": topic_data["title"],
                "weight_percentage": 33.0,
                "competencies": competencies,
                "lecture_content": "Content placeholder...",
                "image": None
            })

        # Mixed Verification Status for Admin Dashboard testing
        is_subject_verified = random.choice([True, True, False]) # 2/3 chance of being verified

        subject_data = {
            "title": sub_info["title"],
            "pqf_level": sub_info["pqf_level"],
            "total_weight_percentage": 100.0,
            "topics": topics,
            "description": sub_info["description"],
            "content": "Syllabus content placeholder.",
            "input_type": "text",
            "is_verified": is_subject_verified,
            "is_active": True,
            "deleted": False,
            "created_by": random.choice(faculty_ids) if faculty_ids else "system",
            "created_at": get_utc_now()
        }
        
        sub_res = await create("subjects", subject_data)
        subject_id = sub_res["id"]
        created_subjects.append({"id": subject_id, "data": subject_data})

        # 2. Create Modules for this Subject
        for _ in range(random.randint(2, 4)):
            is_mod_verified = random.choice([True, True, False])
            
            module_data = {
                "title": f"{fake.word().capitalize()} Module",
                "subject_id": subject_id,
                "purpose": fake.sentence(),
                "bloom_levels": [random.choice(list(BloomTaxonomy))],
                "input_type": "text",
                "content": fake.paragraph(),
                "material_url": "",
                "is_verified": is_mod_verified,
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "created_at": get_utc_now()
            }
            await create("modules", module_data)
            total_modules += 1

        # 3. Create Assessments for this Subject
        if not all_comps_in_subject: continue

        for _ in range(2):
            is_ass_verified = random.choice([True, True, False])
            
            # Generate Questions linked to Competencies
            questions = []
            for q_idx in range(10):
                target_comp = random.choice(all_comps_in_subject)
                
                questions.append({
                    "question_id": str(uuid.uuid4()),
                    "text": f"Question {q_idx+1} regarding {target_comp['description']}?",
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answers": "Option A", 
                    "bloom_taxonomy": target_comp['target_bloom_level'],
                    "difficulty_level": target_comp['target_difficulty'],
                    "competency_id": target_comp['id'], # Linked!
                    "points": 1
                })

            assessment_data = {
                "title": f"{sub_info['title']} {random.choice(['Quiz', 'Exam'])}",
                "type": random.choice(list(AssessmentType)),
                "subject_id": subject_id,
                "total_items": len(questions),
                "questions": questions,
                "is_verified": is_ass_verified,
                "is_rejected": False,
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "description": "Standard assessment.",
                "bloom_levels": list(set([q['bloom_taxonomy'] for q in questions])),
                "created_at": get_utc_now()
            }
            
            ass_res = await create("assessments", assessment_data)
            
            # 4. Create Analytics Data (Submissions) - ONLY if assessment is verified
            if is_ass_verified:
                total_assessments += 1
                await generate_submissions(student_ids, ass_res['id'], assessment_data)

    print(f"   ✅ Created: {len(created_subjects)} Subjects, {total_modules} Modules, {total_assessments} Active Assessments")

async def generate_submissions(student_ids, assessment_id, assessment_data):
    """Simulates students taking the assessment."""
    questions = assessment_data['questions']
    
    # Randomly select 70% of students to have taken this assessment
    taking_students = random.sample(student_ids, k=int(len(student_ids) * 0.7))
    
    for uid in taking_students:
        # Simulate student performance
        ability = random.uniform(0.3, 0.95) # Student ability 30% to 95%
        
        answers = []
        correct_count = 0
        
        for q in questions:
            # Chance to answer correctly based on ability
            is_correct = random.random() < ability
            if is_correct: correct_count += 1
            
            answers.append({
                "question_id": q['question_id'],
                "is_correct": is_correct,
                "competency_id": q['competency_id'],
                "bloom_taxonomy": q['bloom_taxonomy']
            })
        
        score = (correct_count / len(questions)) * 100
        
        submission = {
            "user_id": uid,
            "assessment_id": assessment_id,
            "subject_id": assessment_data['subject_id'],
            "score": score,
            "total_items": len(questions),
            "time_taken_seconds": random.randint(300, 3600),
            "answers": answers,
            "submitted_at": get_utc_now() - timedelta(days=random.randint(1, 30)),
            "created_at": get_utc_now()
        }
        await create("assessment_submissions", submission)
        
        # Also create a study log for this interaction
        await create("study_logs", {
            "user_id": uid,
            "resource_id": assessment_id,
            "resource_type": "assessment",
            "start_time": get_utc_now() - timedelta(days=random.randint(1, 30)),
            "duration_seconds": random.randint(300, 3600),
            "completion_status": ProgressStatus.COMPLETED,
            "created_at": get_utc_now()
        })

async def main():
    print("🚀 STARTING POPULATION")
    print("==================================")
    
    # 1. Setup Roles
    role_ids = await setup_roles()
    
    # 2. Create Users (and Whitelist them)
    student_ids, faculty_ids = await generate_users(role_ids)
    
    # 3. Create Content & Analytics
    # This function creates Subjects -> Modules -> Assessments -> Submissions
    await generate_content(student_ids, faculty_ids)
    
    print("\n==================================")
    print("✨ POPULATION COMPLETE")
    print("   - Users are in 'user_profiles' AND 'whitelist'")
    print("   - Subjects have Topics and Competencies")
    print("   - Mixed Verification status (check Admin Dashboard)")
    print("   - Analytics data generated for verified assessments")

if __name__ == "__main__":
    asyncio.run(main())