import asyncio
import sys
import os
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker
from firebase_admin import auth

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.firebase import db
from services.crud_services import create, read_query, read_one, update
from database.enums import (
    BloomTaxonomy, DifficultyLevel, QuestionType, UserRole,
    PersonalReadinessLevel, ProgressStatus, AssessmentType,
)

fake = Faker()
TEST_PREFIX = "test_auto_"
NUM_STUDENTS = 10
NUM_FACULTY = 3
DEFAULT_PASSWORD = "TestPassword123!"
USER_COLLECTION = "user_profiles"

# --- 4 CORE SUBJECTS DATA ---
SUBJECT_DATA = [
    {
        "title": "Theories of Personality",
        "description": "Study of various theories of personality structure, dynamics, and development.",
        "pqf_level": 6,
        "topics": [
            {"title": "Psychoanalytic Theory", "comps": ["Analyze Freud’s psychosexual stages", "Evaluate defense mechanisms"]},
            {"title": "Neopsychoanalytic Theories", "comps": ["Compare Adler, Jung, and Horney", "Analyze collective unconscious"]},
            {"title": "Humanistic & Existential", "comps": ["Apply Maslow’s hierarchy", "Evaluate Rogers’ person-centered approach"]},
            {"title": "Behavioral Learning", "comps": ["Differentiate classical vs operant conditioning", "Analyze Bandura’s modeling"]},
            {"title": "Trait & Cognitive Theories", "comps": ["Assess Big Five traits", "Apply Kelly’s personal construct theory"]},
        ]
    },
    {
        "title": "Abnormal Psychology",
        "description": "Study of the nature, causes, and treatment of mental disorders.",
        "pqf_level": 6,
        "topics": [
            {"title": "Anxiety & Mood Disorders", "comps": ["Identify symptoms of GAD", "Differentiate Bipolar I & II"]},
            {"title": "Schizophrenia Spectrum", "comps": ["Analyze positive vs negative symptoms", "Evaluate biological causes"]},
            {"title": "Personality Disorders", "comps": ["Differentiate Cluster A, B, and C", "Apply diagnostic criteria"]},
            {"title": "Neurodevelopmental Disorders", "comps": ["Identify ADHD and Autism spectrum", "Evaluate learning disorders"]},
            {"title": "Trauma & Stressors", "comps": ["Analyze PTSD triggers", "Evaluate acute stress disorder"]},
        ]
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
            {"title": "Organizational Culture", "comps": ["Assess leadership styles", "Analyze team dynamics"]},
        ]
    },
    {
        "title": "Psychological Assessment",
        "description": "Principles of psychological testing and measurement.",
        "pqf_level": 6,
        "topics": [
            {"title": "Psychometrics", "comps": ["Calculate reliability coefficients", "Interpret validity evidence"]},
            {"title": "Test Construction", "comps": ["Write effective test items", "Perform item analysis"]},
            {"title": "Intelligence Testing", "comps": ["Interpret WAIS-IV scores", "Analyze theories of intelligence"]},
            {"title": "Personality Assessment", "comps": ["Interpret MMPI-2 profiles", "Evaluate projective tests"]},
            {"title": "Clinical Assessment", "comps": ["Conduct intake interviews", "Integrate assessment data"]},
        ]
    },
]

def get_utc_now():
    return datetime.now(timezone.utc)

async def create_auth_user(email, role_label):
    try:
        try:
            old_user = auth.get_user_by_email(email)
            auth.delete_user(old_user.uid)
        except: pass
        user = auth.create_user(
            email=email, password=DEFAULT_PASSWORD,
            display_name=f"{role_label.capitalize()} User", email_verified=True,
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

async def create_whitelist_entry(email, role):
    existing = await read_query("whitelist", [("email", "==", email)])
    if not existing:
        await create("whitelist", {"email": email, "assigned_role": role, "is_registered": True, "created_at": get_utc_now()})

async def reset_database():
    print("\n🧹 Resetting Database...")
    collections = ["roles", "user_profiles", "whitelist", "subjects", "modules", "assessments", "questions", "assessment_submissions", "study_logs", "notifications"]
    for name in collections:
        docs = list(db.collection(name).list_documents())
        if docs:
            batch = db.batch()
            for doc in docs: batch.delete(doc)
            batch.commit()
            print(f"   - {name}: {len(docs)} deleted")

async def generate_users(role_ids):
    print("\n👥 Generating Users...")
    faculty_ids, student_ids = [], []

    # Admin
    admin_id = await create_auth_user(f"{TEST_PREFIX}admin@cvsu.edu.ph", "admin")
    if admin_id:
        await create(USER_COLLECTION, {
            "email": f"{TEST_PREFIX}admin@cvsu.edu.ph", "first_name": "System", "last_name": "Admin", "username": "sysadmin",
            "role_id": role_ids["admin"], "role": "admin", "is_verified": True, "is_active": True, "is_registered": True,
            "created_at": get_utc_now()
        }, doc_id=admin_id)
        await create_whitelist_entry(f"{TEST_PREFIX}admin@cvsu.edu.ph", UserRole.ADMIN)

    # Faculty
    for i in range(NUM_FACULTY):
        email = f"{TEST_PREFIX}faculty_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "faculty")
        if uid:
            await create(USER_COLLECTION, {
                "email": email, "first_name": fake.first_name(), "last_name": fake.last_name(), "username": f"faculty_{i}",
                "role_id": role_ids["faculty"], "role": "faculty_member", "is_verified": True, "is_active": True, "is_registered": True,
                "created_at": get_utc_now()
            }, doc_id=uid)
            faculty_ids.append(uid)
            await create_whitelist_entry(email, UserRole.FACULTY)

    # Students
    for i in range(NUM_STUDENTS):
        email = f"{TEST_PREFIX}student_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "student")
        if uid:
            student_info = {
                "personal_readiness": "VERY_LOW", 
                "progress_report": [],
                "timeliness": random.randint(60, 100),
                "confident_subject": [], 
                "recommended_study_modules": [], 
                "behavior_profile": {"average_session_length": 0, "learning_pace": "Standard", "preferred_study_time": "Any", "interruption_frequency": "Low"},
                "competency_performance": []
            }
            await create(USER_COLLECTION, {
                "email": email, "first_name": fake.first_name(), "last_name": fake.last_name(), "username": f"student_{i}",
                "role_id": role_ids["student"], "role": "student", "is_verified": True, "is_active": True, "is_registered": True,
                "profile_picture": None,
                "student_info": student_info,
                "created_at": get_utc_now()
            }, doc_id=uid)
            student_ids.append(uid)
            await create_whitelist_entry(email, UserRole.STUDENT)

    return student_ids, faculty_ids

async def generate_content(faculty_ids):
    print("\n📚 Generating Curriculum & Assessments...")
    content_map = [] 
    
    DUMMY_PDF = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    bloom_levels = [b.value for b in BloomTaxonomy]

    # --- PROCESS EACH SUBJECT ---
    for sub_info in SUBJECT_DATA:
        # 1. Create Subject
        topics_data = []
        for topic in sub_info["topics"]:
            comps_data = []
            for c in topic["comps"]:
                comps_data.append({
                    "id": str(uuid.uuid4()), "code": f"C-{random.randint(100,999)}", "description": c,
                    "target_bloom_level": "understanding", "target_difficulty": "moderate", "allocated_items": 5
                })
            topics_data.append({
                "id": str(uuid.uuid4()), "title": topic["title"], "weight_percentage": 20, "competencies": comps_data
            })

        sub_res = await create("subjects", {
            "title": sub_info["title"], "description": sub_info["description"], "pqf_level": 6, "total_weight_percentage": 100,
            "icon_name": "book", "icon_color": "#000000", "icon_bg_color": "#ffffff", "image_url": None,
            "topics": topics_data, "is_verified": True, "is_active": True, "deleted": False,
            "created_by": random.choice(faculty_ids) if faculty_ids else "system",
            "created_at": get_utc_now()
        })
        subject_id = sub_res["id"]
        
        # --- 2. GENERATE DIAGNOSTIC (5 Questions PER SUBJECT) ---
        # [FIX] Creates a specific Diagnostic Assessment for THIS subject
        diag_q = []
        for i in range(5):
            comp_txt = sub_info["topics"][i % 5]["comps"][0]
            q_res = await create("questions", {
                "text": f"Diagnostic: A question about {comp_txt}?",
                "type": QuestionType.MULTIPLE_CHOICE,
                "choices": ["Correct Answer", "Distractor A", "Distractor B", "Distractor C"],
                "correct_answers": "Correct Answer",
                "bloom_taxonomy": random.choice(bloom_levels), "difficulty_level": DifficultyLevel.MODERATE,
                "competency_id": "comp_" + uuid.uuid4().hex[:6],
                "is_verified": True, "points": 1,
                "tags": ["Diagnostic", sub_info['title']], 
                "created_at": get_utc_now()
            })
            diag_q.append({
                "question_id": q_res["id"], "text": f"Diagnostic Q", 
                "choices": ["Correct Answer","Distractor A","Distractor B","Distractor C"], 
                "correct_answers": "Correct Answer", "points": 1, "subject": sub_info["title"]
            })

        # Create the Diagnostic Assessment Linked to THIS Subject
        diag_res = await create("assessments", {
            "title": f"Diagnostic - {sub_info['title']}",
            "type": AssessmentType.DIAGNOSTIC,
            "subject_id": subject_id, 
            "description": f"Baseline assessment for {sub_info['title']}",
            "questions": diag_q,
            "total_items": 5,
            "is_verified": True,
            "created_at": get_utc_now()
        })
        
        subject_structure = {"id": subject_id, "modules": [], "diagnostic_id": diag_res["id"], "post_assessment": None}

        # --- 3. MODULES & QUIZZES ---
        for topic in sub_info["topics"]:
            input_type = random.choice(["pdf", "text"])
            mod_content = f"# {topic['title']}\n\n## Content\nLearn about **{topic['title']}**." if input_type == "text" else None
            
            mod_res = await create("modules", {
                "title": f"Module: {topic['title']}", "subject_id": subject_id, "input_type": input_type,
                "content": mod_content, "material_url": DUMMY_PDF if input_type == "pdf" else None,
                "bloom_levels": [random.choice(bloom_levels)], "purpose": "Educational",
                "is_verified": True, "author": "Dr. " + fake.last_name(),
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "created_at": get_utc_now(), "deleted": False
            })
            module_id = mod_res["id"]

            # Quiz Questions (5 per Module)
            quiz_questions = []
            for k in range(5):
                comp = topic["comps"][k % len(topic["comps"])]
                q_res = await create("questions", {
                    "text": f"Quiz Q{k+1}: {comp}?", "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": ["Option A", "Option B", "Option C", "Option D"], "correct_answers": "Option A",
                    "bloom_taxonomy": random.choice(bloom_levels), "difficulty_level": "moderate",
                    "is_verified": True, "created_at": get_utc_now()
                })
                quiz_questions.append({"question_id": q_res["id"], "text": f"Quiz Q", "choices": ["Option A", "Option B", "Option C", "Option D"], "correct_answers": "Option A", "points": 1, "subject": sub_info["title"]})

            # Create Quiz
            quiz_res = await create("assessments", {
                "title": f"Quiz: {topic['title']}", "type": AssessmentType.QUIZ,
                "subject_id": subject_id, "module_id": module_id, "questions": quiz_questions,
                "total_items": len(quiz_questions), "is_verified": True, "created_at": get_utc_now()
            })
            
            subject_structure["modules"].append({"id": module_id, "quiz_id": quiz_res["id"]})

        # --- 4. POST-ASSESSMENT ---
        if subject_structure["modules"]:
            post_questions = []
            for _ in range(20): 
                 q_res = await create("questions", {
                    "text": f"Final Exam Question for {sub_info['title']}?", "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": ["A", "B", "C", "D"], "correct_answers": "A",
                    "bloom_taxonomy": "analyzing", "difficulty_level": "difficult",
                    "is_verified": True, "created_at": get_utc_now()
                })
                 post_questions.append({"question_id": q_res["id"], "text": "Q", "choices": ["A", "B", "C", "D"], "correct_answers": "A", "subject": sub_info["title"]})

            pa_res = await create("assessments", {
                "title": f"{sub_info['title']} - Final Exam", "type": AssessmentType.POST_ASSESSMENT,
                "subject_id": subject_id, "description": "Comprehensive exam.",
                "questions": post_questions, "total_items": 20,
                "is_verified": True, "created_at": get_utc_now()
            })
            subject_structure["post_assessment"] = pa_res["id"]
        
        content_map.append(subject_structure)

    return content_map

async def simulate_student_activity(student_ids, content_map):
    print("\n🏃 Simulating Student Analytics...")
    
    for idx, uid in enumerate(student_ids):
        persona = "newbie"
        if idx >= 4 and idx <= 6: persona = "learner"
        if idx > 6: persona = "master"
        
        if persona == "newbie": continue 

        # Learner & Master: Take ALL Subject Diagnostics
        # [FIX] This updates analytics for EACH subject individually
        for sub in content_map:
            await create("assessment_submissions", {
                "user_id": uid, "assessment_id": sub["diagnostic_id"], "subject_id": sub["id"],
                "score": 4 if persona == "learner" else 5, "total_items": 5,
                "created_at": get_utc_now() - timedelta(days=60)
            })
        
        progress_reports = []
        best_subject_id = None
        
        # Modules & Quizzes
        for sub in content_map:
            if persona == "learner" and random.random() > 0.6: continue 

            modules_to_do = sub["modules"]
            mod_sum, assess_sum = 0, 0
            
            for mod in modules_to_do:
                await create("study_logs", {
                    "user_id": uid, "resource_id": mod["id"], "resource_type": "module",
                    "duration_seconds": 1200, "start_time": get_utc_now(), "completion_status": ProgressStatus.COMPLETED,
                    "created_at": get_utc_now()
                })
                mod_sum += 100
                
                await create("assessment_submissions", {
                    "user_id": uid, "assessment_id": mod["quiz_id"], "module_id": mod["id"], "subject_id": sub["id"],
                    "score": 5, "total_items": 5, "created_at": get_utc_now()
                })
                assess_sum += 100
            
            avg_mod = int(mod_sum / len(sub["modules"]))
            avg_assess = int(assess_sum / len(sub["modules"]))
            overall = int((avg_mod + avg_assess) / 2)
            
            if overall > 80: best_subject_id = sub["id"]

            progress_reports.append({
                "subject_id": sub["id"], "modules_completeness": avg_mod,
                "assessment_completeness": avg_assess, "overall_completeness": overall,
                "weakest_competencies": []
            })
        
        await update(USER_COLLECTION, uid, {
            "student_info": {
                "personal_readiness": "HIGH" if persona == "master" else "MODERATE",
                "progress_report": progress_reports,
                "timeliness": 90,
                "confident_subject": [best_subject_id] if best_subject_id else [],
                "recommended_study_modules": [],
                "behavior_profile": {"average_session_length": 30, "learning_pace": "Standard"}
            },
            "personal_readiness": "HIGH" if persona == "master" else "MODERATE",
            "has_taken_diagnostic": True 
        })

    print("   ✅ Simulation Complete")

async def main():
    print("🚀 STARTING REALISTIC SCENARIO POPULATION")
    print("=" * 60)
    await reset_database()
    role_ids = await setup_roles()
    student_ids, faculty_ids = await generate_users(role_ids)
    content_map = await generate_content(faculty_ids)
    await simulate_student_activity(student_ids, content_map)
    print("\n✨ POPULATION FINISHED!")
    print(f"   - Newbie: {TEST_PREFIX}student_0@cvsu.edu.ph")
    print(f"   - Master: {TEST_PREFIX}student_9@cvsu.edu.ph")

if __name__ == "__main__":
    asyncio.run(main())