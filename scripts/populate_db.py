import asyncio
import sys
import os
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker
from firebase_admin import auth

# ---------------------------------------------------------
# PATH & DIRECTORY SETUP
# ---------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)
# ---------------------------------------------------------

from core.firebase import db
from services.crud_services import create, read_query, read_one, update
from database.enums import (
    BloomTaxonomy, DifficultyLevel, QuestionType, UserRole,
    PersonalReadinessLevel, ProgressStatus, AssessmentType,
)

fake = Faker()
TEST_PREFIX = "test_auto_"
NUM_STUDENTS = 20
NUM_FACULTY = 4
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
            {"title": "Biological Perspectives", "comps": ["Evaluate genetic influences", "Analyze evolutionary psychology"]},
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
            {"title": "Therapeutic Interventions", "comps": ["Compare CBT and DBT", "Evaluate psychopharmacology"]},
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
            {"title": "Organizational Change", "comps": ["Manage resistance to change", "Evaluate OD interventions"]},
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
            {"title": "Ethical Guidelines", "comps": ["Apply code of ethics", "Evaluate cultural fairness"]},
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
            email=email, 
            password=DEFAULT_PASSWORD,
            display_name=f"{role_label.capitalize()} User", 
            email_verified=True,
        )
        return user.uid
    except Exception as e:
        print(f"   ⚠️ Auth Error ({email}): {e}")
        return None

async def setup_roles():
    print("🔑 Setting up Roles...")
    roles = {"admin": "admin", "student": "student", "faculty": "faculty_member"} 
    role_ids = {}
    for key, designation in roles.items():
        existing = await read_one("roles", designation)
        if not existing:
            await create("roles", {"designation": designation}, doc_id=designation)
        role_ids[key] = designation
    return role_ids

async def create_whitelist_entry(email, role):
    existing = await read_query("whitelist", [("email", "==", email)])
    if not existing:
        await create("whitelist", {
            "email": email, 
            "assigned_role": role, 
            "is_registered": True, 
            "created_at": get_utc_now()
        })

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

    # 1. Admin
    admin_id = await create_auth_user(f"{TEST_PREFIX}admin@cvsu.edu.ph", "admin")
    if admin_id:
        await create(USER_COLLECTION, {
            "email": f"{TEST_PREFIX}admin@cvsu.edu.ph", "first_name": "System", "last_name": "Admin", "username": "sysadmin",
            "role_id": role_ids["admin"], "role": "admin", "is_verified": True, "is_active": True, "is_registered": True,
            "created_at": get_utc_now()
        }, doc_id=admin_id)
        await create_whitelist_entry(f"{TEST_PREFIX}admin@cvsu.edu.ph", UserRole.ADMIN)

    # 2. Faculty
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
            await create_whitelist_entry(email, "faculty_member")

    # 3. Students
    for i in range(NUM_STUDENTS):
        email = f"{TEST_PREFIX}student_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "student")
        if uid:
            is_active = i < (NUM_STUDENTS - 2) 
            
            student_info = {
                "personal_readiness": random.choice([e.value for e in PersonalReadinessLevel]) if is_active else None,
                "progress_report": [],
                "timeliness": random.randint(60, 100) if is_active else 0,
                "confident_subject": [], 
                "recommended_study_modules": [], 
                "behavior_profile": {"average_session_length": 45, "learning_pace": "Standard", "preferred_study_time": "Night", "interruption_frequency": "Low"},
                "competency_performance": []
            }
            await create(USER_COLLECTION, {
                "email": email, "first_name": fake.first_name(), "last_name": fake.last_name(), "username": f"student_{i}",
                "role_id": role_ids["student"], "role": "student", 
                "is_verified": is_active, "is_active": is_active, "is_registered": is_active,
                "profile_picture": None,
                "student_info": student_info,
                "created_at": get_utc_now()
            }, doc_id=uid)
            
            if is_active:
                student_ids.append(uid)
                await create_whitelist_entry(email, UserRole.STUDENT)

    return student_ids, faculty_ids

async def generate_content(faculty_ids):
    print("\n📚 Generating Curriculum & Assessments...")
    content_map = [] 
    
    DUMMY_PDF = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    bloom_levels = [b.value for b in BloomTaxonomy]

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
                "id": str(uuid.uuid4()), "title": topic["title"], "weight_percentage": 16.66, "competencies": comps_data
            })

        sub_res = await create("subjects", {
            "title": sub_info["title"], "description": sub_info["description"], "pqf_level": 6, "total_weight_percentage": 100,
            "icon_name": "book", "icon_color": "#000000", "icon_bg_color": "#ffffff", "image_url": None,
            "topics": topics_data, "is_verified": True, "is_active": True, "deleted": False,
            "created_by": random.choice(faculty_ids) if faculty_ids else "system",
            "created_at": get_utc_now()
        })
        subject_id = sub_res["id"]
        
        # 2. DIAGNOSTIC ASSESSMENT
        diag_q_list = []
        for i in range(5):
            comp_txt = sub_info["topics"][i % 6]["comps"][0]
            q_res = await create("questions", {
                "text": f"Diagnostic Q{i+1}: What is the core concept of {comp_txt}?",
                "type": QuestionType.MULTIPLE_CHOICE,
                "choices": ["Correct Answer", "A", "B", "C"],
                "correct_answers": "Correct Answer",
                "bloom_taxonomy": BloomTaxonomy.REMEMBERING.value, # Diagnostic is basic recall
                "difficulty_level": DifficultyLevel.MODERATE,
                "competency_id": "comp_" + uuid.uuid4().hex[:6],
                "subject_id": subject_id,
                "is_verified": True, "points": 1,
                "tags": ["Diagnostic", sub_info['title']], 
                "created_at": get_utc_now()
            })
            diag_q_list.append({
                "question_id": q_res["id"], "text": "Diagnostic Q", 
                "choices": ["Correct","A","B","C"], "correct_answers": "Correct", "points": 1, "subject": sub_info["title"]
            })

        diag_res = await create("assessments", {
            "title": f"Diagnostic - {sub_info['title']}",
            "type": AssessmentType.DIAGNOSTIC, 
            "subject_id": subject_id, 
            "description": f"Baseline assessment for {sub_info['title']}",
            "questions": diag_q_list,
            "total_items": 5,
            "is_verified": True,
            "created_at": get_utc_now(),
            "bloom_levels": [BloomTaxonomy.REMEMBERING.value, BloomTaxonomy.UNDERSTANDING.value] # <--- ADDED: Diagnostic is foundational
        })
        
        subject_structure = {"id": subject_id, "modules": [], "diagnostic_id": diag_res["id"], "post_assessment": None}

        # 3. MODULES & QUIZZES
        for idx, topic in enumerate(sub_info["topics"]):
            input_type = "pdf" if idx < 3 else "text"
            
            # Module Bloom Level (Random, but used for Quiz)
            module_bloom_level = random.choice([
                BloomTaxonomy.UNDERSTANDING.value, 
                BloomTaxonomy.APPLYING.value, 
                BloomTaxonomy.ANALYZING.value
            ])
            
            # Rich Subject-Specific Content
            if input_type == "text":
                topic_title = topic['title']
                learning_objs = "\n".join([f"* {c}" for c in topic['comps']])
                
                mod_content = f"""# {topic_title}

## 1. Introduction to {topic_title}
This module explores **{topic_title}** within the domain of **{sub_info['title']}**. It is critical for the Psychometrician licensure examination as it covers fundamental theories and practical applications.

## 2. Learning Objectives
By the end of this module, you should be able to:
{learning_objs}

## 3. Core Concepts and Analysis
In studying {topic_title}, we examine the underlying mechanisms that drive behavior. 

### Key Principles:
* **Theoretical Foundation:** Understanding the history and development of these concepts.
* **Practical Application:** How to apply {topic_title} in clinical or industrial settings.
* **Critical Analysis:** Evaluating the strengths and limitations of current models.

## 4. Summary
To summarize, mastering {topic_title} requires a deep understanding of its components and how they interact with other areas of {sub_info['title']}.

> **Study Tip:** Focus on the competencies listed above for your upcoming quiz.
"""
            else:
                mod_content = None
            
            mod_res = await create("modules", {
                "title": f"Module {idx+1}: {topic['title']}", 
                "subject_id": subject_id, 
                "subject_title": sub_info["title"], 
                "input_type": input_type,
                "content": mod_content, 
                "material_url": DUMMY_PDF if input_type == "pdf" else None,
                "bloom_levels": [module_bloom_level], # Storing the module's primary bloom level
                "purpose": "Educational",
                "is_verified": True, 
                "author": "Faculty Department",
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "created_at": get_utc_now(), "deleted": False
            })
            module_id = mod_res["id"]

            # Quiz Questions (Inherits Module Bloom Level)
            quiz_questions = []
            for k in range(5):
                comp = topic["comps"][k % len(topic["comps"])]
                q_res = await create("questions", {
                    "text": f"Quiz Question: Regarding {topic['title']}, how would you {comp.lower()}?", 
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": ["Option A", "Option B", "Option C", "Option D"], 
                    "correct_answers": "Option A",
                    "bloom_taxonomy": module_bloom_level, # Question matches module
                    "difficulty_level": DifficultyLevel.MODERATE,
                    "competency_id": "comp_" + uuid.uuid4().hex[:6],
                    "subject_id": subject_id, "module_id": module_id,
                    "is_verified": True, "created_at": get_utc_now()
                })
                quiz_questions.append({"question_id": q_res["id"], "text": "Quiz Q", "choices": ["A","B","C","D"], "correct_answers": "A", "points": 1})

            quiz_res = await create("assessments", {
                "title": f"Quiz: {topic['title']}", "type": AssessmentType.QUIZ,
                "subject_id": subject_id, "module_id": module_id, "questions": quiz_questions,
                "total_items": 5, 
                "is_verified": True, 
                "created_at": get_utc_now(),
                "bloom_levels": [module_bloom_level] # <--- ADDED: Quiz inherits module's bloom level
            })
            
            subject_structure["modules"].append({"id": module_id, "quiz_id": quiz_res["id"]})

        # 4. POST-ASSESSMENT (Higher Order)
        post_q_list = []
        for j in range(10): 
             topic_ctx = random.choice(sub_info["topics"])["title"]
             q_res = await create("questions", {
                "text": f"Final Exam: Comprehensive analysis of {topic_ctx} in {sub_info['title']}.", 
                "type": QuestionType.MULTIPLE_CHOICE,
                "choices": ["Theory A is correct", "Theory B applies here", "Both A and B", "Neither A nor B"], 
                "correct_answers": "Theory A is correct",
                "bloom_taxonomy": BloomTaxonomy.ANALYZING.value, # Question is Analysis/Evaluation
                "difficulty_level": DifficultyLevel.DIFFICULT,
                "competency_id": "comp_" + uuid.uuid4().hex[:6],
                "subject_id": subject_id,
                "is_verified": True, "created_at": get_utc_now()
            })
             post_q_list.append({"question_id": q_res["id"], "text": "Q", "choices": ["A","B","C","D"], "correct_answers": "A", "points": 1, "subject": sub_info["title"]})

        pa_res = await create("assessments", {
            "title": f"{sub_info['title']} - Final Exam", 
            "type": AssessmentType.POST_ASSESSMENT,
            "subject_id": subject_id, 
            "description": "Comprehensive exam covering all modules.",
            "questions": post_q_list, "total_items": 10, 
            "is_verified": True,
            "created_at": get_utc_now(),
            "bloom_levels": [BloomTaxonomy.ANALYZING.value, BloomTaxonomy.EVALUATING.value] # <--- ADDED: Post-Assessment is high order
        })
        subject_structure["post_assessment"] = pa_res["id"]
        
        # 5. GENERATE PENDING MATERIALS
        print(f"   - Generating pending materials for {sub_info['title']}...")
        
        for p in range(3):
            p_content = f"# Draft: Advanced {sub_info['title']} Concept\n\n## Overview\nThis content is currently under review by the department head. It covers advanced applications of **{sub_info['topics'][0]['title']}**.\n\n## Objectives\n* Critical analysis\n* Theoretical application"
            
            await create("modules", {
                "title": f"Pending Module {p+1}: {sub_info['title']} Advanced", 
                "subject_id": subject_id, 
                "subject_title": sub_info["title"], 
                "input_type": "text",
                "content": p_content, 
                "bloom_levels": [BloomTaxonomy.CREATING.value], # Pending module is creating level
                "purpose": "Supplemental",
                "is_verified": False, # <--- PENDING
                "author": "Dr. Pending",
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "created_at": get_utc_now(), "deleted": False
            })
            
            await create("assessments", {
                "title": f"Proposed Quiz {p+1}", 
                "type": AssessmentType.QUIZ,
                "subject_id": subject_id, 
                "questions": [],
                "total_items": 0, 
                "is_verified": False, # <--- PENDING
                "created_at": get_utc_now(),
                "bloom_levels": [BloomTaxonomy.REMEMBERING.value] # Pending Quiz
            })

        content_map.append(subject_structure)

    return content_map

async def simulate_student_activity(student_ids, content_map):
    print("\n🏃 Simulating Student Analytics...")
    
    for idx, uid in enumerate(student_ids):
        persona = "newbie"
        if idx >= 7 and idx <= 13: persona = "learner"
        if idx > 13: persona = "master"
        
        if persona == "newbie": continue 

        # Learner & Master: Take Diagnostics
        for sub in content_map:
            await create("assessment_submissions", {
                "user_id": uid, "assessment_id": sub["diagnostic_id"], "subject_id": sub["id"],
                "score": 4 if persona == "learner" else 5, "total_items": 5, "percentage": 80 if persona == "learner" else 100,
                "created_at": get_utc_now() - timedelta(days=60)
            })
        
        progress_reports = []
        best_subject_id = None
        
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
                    "score": 5, "total_items": 5, "percentage": 100, "created_at": get_utc_now()
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
                "user_id": uid,
                "personal_readiness": "HIGH" if persona == "master" else "MODERATE",
                "progress_report": progress_reports,
                "timeliness": 90,
                "confident_subject": [best_subject_id] if best_subject_id else [],
                "recommended_study_modules": [],
                "behavior_profile": {"average_session_length": 30, "learning_pace": "Standard"}
            },
            "has_taken_diagnostic": True 
        })

    print("   ✅ Simulation Complete")

async def create_pending_whitelists():
    print("\n📝 Creating 5 Pending Whitelists...")
    pending_emails = [
        f"pending_prof_{i}@cvsu.edu.ph" for i in range(1, 4)
    ] + [f"pending_student_{i}@cvsu.edu.ph" for i in range(1, 3)]
    
    for email in pending_emails:
        role = "faculty_member" if "prof" in email else "student"
        await create("whitelist", {
            "email": email, 
            "assigned_role": role, 
            "is_registered": False, # <--- PENDING
            "created_at": get_utc_now()
        })
    print(f"   Created {len(pending_emails)} whitelist entries.")

async def main():
    print("🚀 STARTING REALISTIC SCENARIO POPULATION")
    print("=" * 60)
    await reset_database()
    role_ids = await setup_roles()
    student_ids, faculty_ids = await generate_users(role_ids)
    content_map = await generate_content(faculty_ids)
    await simulate_student_activity(student_ids, content_map)
    await create_pending_whitelists()
    
    print("\n✨ POPULATION FINISHED!")
    print(f"   - Newbie: {TEST_PREFIX}student_0@cvsu.edu.ph")
    print(f"   - Master: {TEST_PREFIX}student_19@cvsu.edu.ph")

if __name__ == "__main__":
    asyncio.run(main())