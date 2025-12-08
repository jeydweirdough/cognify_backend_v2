import asyncio
import sys
import os
import random
import uuid
from datetime import datetime, timezone
from faker import Faker
from firebase_admin import auth

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Initialize Firebase
from core.firebase import db
from services.crud_services import create, read_query, read_one, delete
from database.enums import (
    BloomTaxonomy,
    DifficultyLevel,
    QuestionType,
    UserRole,
    AssessmentType,
)

fake = Faker()

# --- CONFIGURATION ---
TEST_PREFIX = "test_auto_"
ADMIN_EMAIL = f"{TEST_PREFIX}admin@cvsu.edu.ph"
DEFAULT_PASSWORD = "TestPassword123!"
USER_COLLECTION = "user_profiles"

# --- 4 CORE SUBJECTS (5 Topics Each) ---
SUBJECT_DATA = [
    {
        "title": "Theories of Personality",
        "description": "Study of various theories of personality structure, dynamics, and development.",
        "pqf_level": 6,
        "topics": [
            {"title": "Psychoanalytic Theory (Freud)", "comps": ["Analyze psychosexual stages", "Evaluate defense mechanisms"]},
            {"title": "Neopsychoanalytic Theories", "comps": ["Compare Adler, Jung, and Horney", "Analyze collective unconscious"]},
            {"title": "Humanistic & Existential", "comps": ["Apply Maslow’s hierarchy", "Evaluate Rogers’ person-centered approach"]},
            {"title": "Behavioral & Social Learning", "comps": ["Differentiate classical/operant conditioning", "Analyze Bandura’s observational learning"]},
            {"title": "Trait & Cognitive Theories", "comps": ["Assess Big Five traits", "Apply Kelly’s personal construct theory"]},
        ],
    },
    {
        "title": "Abnormal Psychology",
        "description": "Study of the nature, causes, and treatment of mental disorders.",
        "pqf_level": 6,
        "topics": [
            {"title": "Anxiety & Trauma Disorders", "comps": ["Identify GAD and PTSD symptoms", "Differentiate phobias"]},
            {"title": "Mood Disorders", "comps": ["Analyze Major Depressive Disorder", "Differentiate Bipolar I vs II"]},
            {"title": "Schizophrenia Spectrum", "comps": ["Analyze positive vs negative symptoms", "Evaluate biological causes"]},
            {"title": "Personality Disorders", "comps": ["Differentiate Cluster A, B, and C", "Apply diagnostic criteria"]},
            {"title": "Neurodevelopmental Disorders", "comps": ["Identify ADHD and Autism spectrum", "Evaluate learning disorders"]},
        ],
    },
    {
        "title": "Industrial-Organizational Psychology",
        "description": "Application of psychological principles to the workplace.",
        "pqf_level": 6,
        "topics": [
            {"title": "Job Analysis & Selection", "comps": ["Conduct job analysis", "Develop selection interviews"]},
            {"title": "Performance Appraisal", "comps": ["Design rating scales", "Reduce rater errors"]},
            {"title": "Training & Development", "comps": ["Design training programs", "Evaluate transfer of training"]},
            {"title": "Work Motivation", "comps": ["Apply ERG and Equity theories", "Analyze job satisfaction factors"]},
            {"title": "Organizational Culture", "comps": ["Assess leadership styles", "Analyze group dynamics and conflict"]},
        ],
    },
    {
        "title": "Psychological Assessment",
        "description": "Principles of psychological testing and measurement.",
        "pqf_level": 6,
        "topics": [
            {"title": "Nature & Use of Tests", "comps": ["Define standardization", "Evaluate ethical considerations"]},
            {"title": "Reliability & Validity", "comps": ["Calculate Cronbach's alpha", "Differentiate content vs construct validity"]},
            {"title": "Test Construction", "comps": ["Perform item analysis", "Write effective test items"]},
            {"title": "Intelligence Testing", "comps": ["Interpret WAIS-IV scores", "Analyze theories of intelligence"]},
            {"title": "Personality Assessment", "comps": ["Interpret MMPI-2 profiles", "Evaluate projective tests (Rorschach)"]},
        ],
    },
]

def get_utc_now():
    return datetime.now(timezone.utc)

async def create_auth_user(email):
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
            display_name="System Admin",
            email_verified=True,
        )
        return user.uid
    except Exception as e:
        print(f"   ⚠️ Auth Error ({email}): {e}")
        return None

async def setup_roles():
    print("🔑 Setting up Roles...")
    roles = {"admin": "admin", "student": "student", "faculty": "faculty_member"}
    for key, designation in roles.items():
        if not await read_one("roles", designation):
            await create("roles", {"designation": designation}, doc_id=designation)
    return roles

async def create_whitelist_entry(email, role, adder_id="system"):
    existing = await read_query("whitelist", [("email", "==", email)])
    if not existing:
        await create("whitelist", {
            "email": email,
            "assigned_role": role,
            "is_registered": True, # Admin is pre-registered
            "added_by": adder_id,
            "created_at": get_utc_now(),
        })

# [FIX] Added the missing reset_database function
async def reset_database():
    print("\n🧹 Resetting Database...")
    # List of collections to wipe
    collections = [
        "roles", "user_profiles", "whitelist", "subjects", 
        "modules", "assessments", "questions", "assessment_submissions", 
        "study_logs", "notifications"
    ]
    for name in collections:
        docs = list(db.collection(name).list_documents())
        if docs:
            batch = db.batch()
            for doc in docs: batch.delete(doc)
            batch.commit()
            print(f"   - {name}: {len(docs)} deleted")

async def generate_admin(role_ids):
    print("\n👤 Generating Admin User...")
    
    uid = await create_auth_user(ADMIN_EMAIL)
    if uid:
        await create(USER_COLLECTION, {
            "email": ADMIN_EMAIL,
            "first_name": "System",
            "last_name": "Admin",
            "middle_name": "Root",
            "nickname": "SysAdmin",
            "username": "sysadmin",
            "role_id": role_ids["admin"],
            "role": "admin",
            "is_verified": True,
            "is_active": True,
            "is_registered": True,
            "profile_picture": None,
            "created_at": get_utc_now(),
        }, doc_id=uid)
        await create_whitelist_entry(ADMIN_EMAIL, UserRole.ADMIN, uid)
        print(f"   ✅ Created Admin: {ADMIN_EMAIL}")
        return uid
    return "system"

async def generate_content(admin_id):
    print("\n📚 Generating Curriculum & Assessments...")
    
    DUMMY_PDF = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    bloom_levels = [b.value for b in BloomTaxonomy]
    all_questions_pool = [] 

    # --- 1. GLOBAL DIAGNOSTIC ---
    diag_q = []
    for i in range(10):
        q_bloom = bloom_levels[i % len(bloom_levels)]
        q_res = await create("questions", {
            "text": f"Diagnostic Question {i+1}: Testing {q_bloom} skills.",
            "type": QuestionType.MULTIPLE_CHOICE,
            "choices": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answers": "Option A",
            "bloom_taxonomy": q_bloom,
            "difficulty_level": random.choice([DifficultyLevel.EASY, DifficultyLevel.MODERATE]),
            "is_verified": True,
            "points": 1,
            "created_by": admin_id,
            "created_at": get_utc_now()
        })
        diag_q.append({"question_id": q_res["id"], "text": f"Diagnostic Q{i+1}", "choices": ["A","B","C","D"], "correct_answers": "A", "points": 1})
    
    await create("assessments", {
        "title": "Diagnostic Examination",
        "type": AssessmentType.DIAGNOSTIC,
        "subject_id": "global",
        "description": "Baseline assessment to gauge your readiness.",
        "questions": diag_q,
        "total_items": 10,
        "is_verified": True,
        "created_by": admin_id,
        "created_at": get_utc_now()
    })

    # --- 2. SUBJECTS, MODULES, QUIZZES ---
    for sub_info in SUBJECT_DATA:
        # Create Subject (Admin View Schema)
        topics_data = []
        for topic in sub_info["topics"]:
            comps_data = []
            for c in topic["comps"]:
                comps_data.append({
                    "id": str(uuid.uuid4()),
                    "code": f"C-{random.randint(100,999)}",
                    "description": c,
                    "target_bloom_level": "understanding",
                    "target_difficulty": "moderate",
                    "allocated_items": 5
                })
            topics_data.append({
                "id": str(uuid.uuid4()),
                "title": topic["title"],
                "weight_percentage": 20, # 5 topics * 20 = 100%
                "competencies": comps_data
            })

        sub_res = await create("subjects", {
            "title": sub_info["title"],
            "description": sub_info["description"],
            "pqf_level": sub_info["pqf_level"],
            "total_weight_percentage": 100,
            "icon_name": "book",
            "icon_color": "#000000",
            "icon_bg_color": "#ffffff",
            "image_url": None,
            "topics": topics_data, # Admin schema requirement
            "is_verified": True,
            "is_active": True,
            "deleted": False,
            "created_by": admin_id,
            "created_at": get_utc_now()
        })
        subject_id = sub_res["id"]
        
        subject_structure = {"id": subject_id, "modules": [], "post_assessment": None}

        # Modules -> Quizzes
        for topic in sub_info["topics"]:
            input_type = random.choice(["pdf", "text"])
            mod_content = None
            mod_url = None
            
            if input_type == "text":
                mod_content = f"""# {topic['title']}
## 1. Introduction
This module covers the core concepts of **{topic['title']}**. 

## 2. Key Competencies
{chr(10).join([f'- {c}' for c in topic["comps"]])}

### Summary
Please proceed to the quiz to test your understanding.
"""
            else:
                mod_url = DUMMY_PDF

            mod_res = await create("modules", {
                "title": f"Module: {topic['title']}",
                "subject_id": subject_id,
                "input_type": input_type,
                "content": mod_content,
                "material_url": mod_url,
                "bloom_levels": [random.choice(bloom_levels)],
                "purpose": "Educational",
                "is_verified": True, 
                "author": "System Admin",
                "created_by": admin_id,
                "created_at": get_utc_now(),
                "deleted": False
            })
            module_id = mod_res["id"]

            # Quiz Questions (Subject-Specific)
            quiz_questions = []
            for comp in topic["comps"]:
                q_bloom = random.choice(bloom_levels)
                q_res = await create("questions", {
                    "text": f"Question regarding {comp} in {sub_info['title']}?",
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": ["Correct Answer", "Wrong Option A", "Wrong Option B", "Wrong Option C"],
                    "correct_answers": "Correct Answer",
                    "bloom_taxonomy": q_bloom,
                    "difficulty_level": random.choice([DifficultyLevel.EASY, DifficultyLevel.MODERATE]),
                    "competency_id": "comp_" + uuid.uuid4().hex[:6],
                    "is_verified": True,
                    "points": 1,
                    "tags": [sub_info["title"], "Core"],
                    "created_by": admin_id,
                    "created_at": get_utc_now()
                })
                
                q_obj = {
                    "question_id": q_res["id"], 
                    "text": f"Question regarding {comp}?",
                    "choices": ["Correct Answer", "Wrong Option A", "Wrong Option B", "Wrong Option C"],
                    "correct_answers": "Correct Answer",
                    "points": 1,
                    "subject": sub_info["title"]
                }
                quiz_questions.append(q_obj)

            # Create Quiz
            quiz_res = await create("assessments", {
                "title": f"Quiz: {topic['title']}",
                "type": AssessmentType.QUIZ,
                "subject_id": subject_id,
                "module_id": module_id, 
                "questions": quiz_questions,
                "total_items": len(quiz_questions),
                "is_verified": True,
                "created_by": admin_id,
                "created_at": get_utc_now()
            })
            
            subject_structure["modules"].append({
                "id": module_id,
                "quiz_id": quiz_res["id"]
            })

        # --- 3. POST-ASSESSMENT ---
        if subject_structure["modules"]:
            # Gather questions from modules for the final exam
            post_questions = []
            for _ in range(5):
                 q_res = await create("questions", {
                    "text": f"Final Exam Question for {sub_info['title']}?",
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": ["A", "B", "C", "D"],
                    "correct_answers": "A",
                    "bloom_taxonomy": "analyzing",
                    "difficulty_level": "difficult",
                    "is_verified": True,
                    "created_by": admin_id,
                    "created_at": get_utc_now()
                })
                 post_questions.append({"question_id": q_res["id"], "text": "Q", "choices": ["A"], "correct_answers": "A"})

            await create("assessments", {
                "title": f"{sub_info['title']} - Final Exam",
                "type": AssessmentType.POST_ASSESSMENT,
                "subject_id": subject_id,
                "description": "Comprehensive exam for this subject.",
                "questions": post_questions,
                "total_items": len(post_questions),
                "is_verified": True,
                "created_by": admin_id,
                "created_at": get_utc_now()
            })

async def main():
    print("🚀 STARTING ADMIN & CONTENT POPULATION")
    print("=" * 60)
    await reset_database()
    role_ids = await setup_roles()
    admin_id = await generate_admin(role_ids)
    await generate_content(admin_id)
    print("\n✨ POPULATION FINISHED!")
    print(f"   - Admin: {ADMIN_EMAIL}")
    print(f"   - Password: {DEFAULT_PASSWORD}")
    print("   - Subjects: 4 Core Subjects created")
    print("   - Modules: 20 Modules created (5 per subject)")
    print("   - Assessments: 1 Diagnostic, 20 Quizzes, 4 Post-Assessments")

if __name__ == "__main__":
    asyncio.run(main())