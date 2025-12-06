# scripts/populate_db.py
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

# Initialize Firebase
from core.firebase import db
from services.crud_services import create, read_query, read_one
from database.enums import (
    BloomTaxonomy,
    DifficultyLevel,
    QuestionType,
    UserRole,
    PersonalReadinessLevel,
    ProgressStatus,
    AssessmentType,
)

fake = Faker()

# --- CONFIGURATION ---
TEST_PREFIX = "test_auto_"
NUM_STUDENTS = 15
NUM_FACULTY = 3
DEFAULT_PASSWORD = "TestPassword123!"
USER_COLLECTION = "user_profiles"

# --- DATA DEFINITIONS ---
ROLE_MAP = {"admin": "admin", "student": "student", "faculty": "faculty_member"}

# --- OFFICIAL PSYCHOMETRICIAN TOS BLUEPRINT ---
# Updated to match PRC Board Exam Weights and Cognitive Levels
SUBJECT_DATA = [
    {
        "title": "Psychological Assessment",
        "description": "Principles of testing, test construction, and usage.",
        "pqf_level": 6,
        "total_weight_percentage": 40.0, # Heaviest weight
        "topics": [
            {
                "title": "Test Construction & Standardization",
                "comps": [
                    {"desc": "Apply methods of item analysis (difficulty & discrimination)", "bloom": "analyzing"},
                    {"desc": "Establish reliability and validity of instruments", "bloom": "evaluating"},
                    {"desc": "Define norms and standardization procedures", "bloom": "remembering"}
                ],
            },
            {
                "title": "Handling Assessment Tools",
                "comps": [
                    {"desc": "Administer and score objective personality tests", "bloom": "applying"},
                    {"desc": "Interpret standardized test results", "bloom": "analyzing"},
                    {"desc": "Write psychological assessment reports", "bloom": "creating"}
                ],
            },
            {
                "title": "Ethics in Assessment",
                "comps": [
                    {"desc": "Apply ethical principles in testing", "bloom": "applying"},
                    {"desc": "Evaluate cultural fairness in assessment", "bloom": "evaluating"}
                ]
            }
        ],
    },
    {
        "title": "Abnormal Psychology",
        "description": "Psychopathology and maladaptive behaviors.",
        "pqf_level": 6,
        "total_weight_percentage": 20.0,
        "topics": [
            {
                "title": "Anxiety & Mood Disorders",
                "comps": [
                    {"desc": "Differentiate normal anxiety from pathological anxiety", "bloom": "analyzing"},
                    {"desc": "Identify symptoms of Major Depressive Disorder", "bloom": "remembering"},
                    {"desc": "Formulate a diagnosis based on case symptoms", "bloom": "evaluating"}
                ],
            },
            {
                "title": "Schizophrenia Spectrum",
                "comps": [
                    {"desc": "Identify positive and negative symptoms", "bloom": "understanding"},
                    {"desc": "Distinguish between delusions and hallucinations", "bloom": "analyzing"}
                ],
            }
        ],
    },
    {
        "title": "Theories of Personality",
        "description": "Survey of major theories of personality.",
        "pqf_level": 6,
        "total_weight_percentage": 20.0,
        "topics": [
            {
                "title": "Psychoanalytic Perspective",
                "comps": [
                    {"desc": "Explain Freud's psychosexual stages", "bloom": "understanding"},
                    {"desc": "Analyze defense mechanisms in daily life", "bloom": "analyzing"}
                ],
            },
            {
                "title": "Humanistic & Existential",
                "comps": [
                    {"desc": "Compare Maslow and Rogers' theories", "bloom": "analyzing"},
                    {"desc": "Apply concepts of self-actualization", "bloom": "applying"}
                ],
            }
        ],
    },
    {
        "title": "Industrial-Organizational Psychology",
        "description": "Workplace behavior and HR principles.",
        "pqf_level": 6,
        "total_weight_percentage": 20.0,
        "topics": [
            {
                "title": "Recruitment & Selection",
                "comps": [
                    {"desc": "Conduct job analysis for a specific role", "bloom": "applying"},
                    {"desc": "Design a valid selection interview guide", "bloom": "creating"}
                ],
            },
            {
                "title": "Organizational Development",
                "comps": [
                    {"desc": "Evaluate organizational culture", "bloom": "evaluating"},
                    {"desc": "Apply motivation theories to employee retention", "bloom": "applying"}
                ],
            }
        ],
    },
    {
        "title": "Developmental Psychology",
        "description": "Study of human growth and changes.",
        "pqf_level": 6,
        "total_weight_percentage": 0.0,
        "topics": [
            {
                "title": "Piaget's Stages",
                "comps": [
                    {"desc": "Differentiate sensorimotor and preoperational", "bloom": "understanding"},
                    {"desc": "Apply concrete operational concepts", "bloom": "applying"}
                ],
            }
        ]
    }
]

# Generic module content
MODULE_CONTENT_TEMPLATES = [
    "This module covers the fundamental concepts and theories related to the subject matter.",
    "In this section, we explore the main ideas and methodologies used in the field.",
    "This learning material introduces students to essential concepts, definitions, and frameworks.",
    "This module presents a detailed analysis of the core competencies required for mastery.",
    "Students will engage with key theories, research evidence, and practical strategies in this module.",
]

# Sample Questions (Updated to map to new Subjects)
CUSTOM_QUESTIONS = {
    "Psychological Assessment": [
        {"text": "Which type of validity assesses whether a test appears to measure what it claims?", "choices": ["Predictive validity", "Content validity", "Face validity", "Construct validity"], "correct": "Face validity", "bloom": "remembering", "difficulty": "Easy"},
        {"text": "A test that yields consistent results over time is considered:", "choices": ["Valid", "Reliable", "Norm-referenced", "Subjective"], "correct": "Reliable", "bloom": "understanding", "difficulty": "Moderate"},
        {"text": "Which assessment tool is most suitable for measuring intelligence?", "choices": ["Rorschach Inkblot Test", "Wechsler Adult Intelligence Scale (WAIS)", "Beck Depression Inventory", "MMPI"], "correct": "Wechsler Adult Intelligence Scale (WAIS)", "bloom": "remembering", "difficulty": "Easy"},
        {"text": "Calculate the Z-score if the raw score is 115, Mean is 100, and SD is 15.", "choices": ["+1.0", "+2.0", "-1.0", "0.0"], "correct": "+1.0", "bloom": "applying", "difficulty": "Difficult"},
        {"text": "Interpret a percentile rank of 84 in a normal distribution.", "choices": ["Below average", "Average", "One standard deviation above the mean", "Top 1%"], "correct": "One standard deviation above the mean", "bloom": "analyzing", "difficulty": "Difficult"}
    ],
    "Abnormal Psychology": [
        {"text": "Which of the following is classified as a mood disorder?", "choices": ["Schizophrenia", "Bipolar disorder", "OCD", "Panic disorder"], "correct": "Bipolar disorder", "bloom": "remembering", "difficulty": "Easy"},
        {"text": "The main feature of schizophrenia involves:", "choices": ["Excessive worry", "Delusions and hallucinations", "Panic attacks", "Impulsivity"], "correct": "Delusions and hallucinations", "bloom": "understanding", "difficulty": "Moderate"},
        {"text": "Differentiate between Bipolar I and Bipolar II disorders.", "choices": ["Bipolar I has full mania; Bipolar II has hypomania", "Bipolar I has depression only", "Bipolar II is more severe", "They are the same"], "correct": "Bipolar I has full mania; Bipolar II has hypomania", "bloom": "analyzing", "difficulty": "Moderate"},
        {"text": "A patient presents with fear of open spaces. This is:", "choices": ["Claustrophobia", "Agoraphobia", "Social Anxiety", "Panic Disorder"], "correct": "Agoraphobia", "bloom": "analyzing", "difficulty": "Moderate"}
    ],
    "Theories of Personality": [
        {"text": "Which of the following best describes Erikson's stage of identity vs. role confusion?", "choices": ["Developing trust", "Exploring personal values", "Learning motor skills", "Coping with stagnation"], "correct": "Exploring personal values", "bloom": "understanding", "difficulty": "Moderate"},
        {"text": "Freud's Id operates on which principle?", "choices": ["Reality Principle", "Pleasure Principle", "Moral Principle", "Idealistic Principle"], "correct": "Pleasure Principle", "bloom": "remembering", "difficulty": "Easy"},
        {"text": "Identify the defense mechanism: A student fails a test and yells at their sibling.", "choices": ["Projection", "Displacement", "Sublimation", "Denial"], "correct": "Displacement", "bloom": "analyzing", "difficulty": "Difficult"}
    ],
    "Industrial-Organizational Psychology": [
        {"text": "What is the primary goal of job analysis?", "choices": ["Evaluate values", "Identify duties and skills", "Study morale", "Determine financial goals"], "correct": "Identify duties and skills", "bloom": "remembering", "difficulty": "Easy"},
        {"text": "Which theory suggests employees are motivated by Hygiene and Motivator factors?", "choices": ["Maslow's Hierarchy", "Herzberg's Two-Factor Theory", "Vroom's Expectancy", "McGregor's Theory X"], "correct": "Herzberg's Two-Factor Theory", "bloom": "understanding", "difficulty": "Moderate"}
    ]
}

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
            email_verified=True,
        )
        return user.uid
    except Exception as e:
        print(f"   ⚠️ Auth Error ({email}): {e}")
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
    existing = await read_query("whitelist", [("email", "==", email)])
    if existing: return existing[0]["id"]
    entry = {"email": email, "assigned_role": role, "is_registered": True, "added_by": adder_id, "created_at": get_utc_now()}
    res = await create("whitelist", entry)
    return res["id"]

async def generate_users(role_ids):
    print("\n👥 Generating Users & Whitelist...")
    faculty_ids = []
    student_ids = []
    credentials = []

    # Admin
    admin_email = f"{TEST_PREFIX}admin@cvsu.edu.ph"
    uid = await create_auth_user(admin_email, "admin")
    if uid:
        await create(USER_COLLECTION, {"email": admin_email, "first_name": "System", "last_name": "Admin", "username": "sysadmin", "role_id": role_ids["admin"], "is_verified": True, "is_registered": True, "is_active": True, "created_at": get_utc_now()}, doc_id=uid)
        await create_whitelist_entry(admin_email, UserRole.ADMIN, uid)
        credentials.append({"role": "ADMIN", "email": admin_email, "password": DEFAULT_PASSWORD})
        print(f"   ✅ Created Admin: {admin_email}")

    # Faculty
    for i in range(NUM_FACULTY):
        email = f"{TEST_PREFIX}faculty_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "faculty")
        if uid:
            await create(USER_COLLECTION, {"email": email, "first_name": fake.first_name(), "last_name": fake.last_name(), "username": f"faculty_{i}", "role_id": role_ids["faculty"], "is_verified": True, "is_registered": True, "is_active": True, "created_at": get_utc_now()}, doc_id=uid)
            faculty_ids.append(uid)
            await create_whitelist_entry(email, UserRole.FACULTY, "system")
            credentials.append({"role": "FACULTY", "email": email, "password": DEFAULT_PASSWORD})
            print(f"   ✅ Created Faculty: {email}")

    # Students
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
                    "learning_pace": random.choice(["Fast", "Standard", "Standard", "Slow"]),
                    "interruption_frequency": random.choice(["Low", "Medium", "High"]),
                    "average_session_length": random.randint(20, 120),
                    "preferred_study_time": random.choice(["Morning", "Evening", "Any"]),
                },
                "progress_report": [],
                "competency_performance": [],
            }
            await create(USER_COLLECTION, {"email": email, "first_name": fake.first_name(), "last_name": fake.last_name(), "username": f"student_{i}", "role_id": role_ids["student"], "is_verified": True, "is_registered": True, "is_active": True, "student_info": student_info, "created_at": get_utc_now()}, doc_id=uid)
            student_ids.append(uid)
            await create_whitelist_entry(email, UserRole.STUDENT, "system")
            credentials.append({"role": "STUDENT", "email": email, "password": DEFAULT_PASSWORD})

    print(f"   ✅ Created: {len(student_ids)} Students")
    return student_ids, faculty_ids, credentials

async def reset_database():
    print("\n🧹 Resetting Database...")
    collections = ["roles", USER_COLLECTION, "whitelist", "subjects", "modules", "assessments", "questions", "assessment_submissions", "study_logs", "competencies"]
    for name in collections:
        try:
            col_ref = db.collection(name)
            docs = list(col_ref.list_documents())
            if docs:
                batch = db.batch()
                for doc_ref in docs: batch.delete(doc_ref)
                batch.commit()
                print(f"   - {name}: {len(docs)} deleted")
        except Exception as e: print(f"   ⚠️ {name} reset failed: {e}")

async def generate_content(student_ids, faculty_ids):
    print("\n📚 Generating Content (Subjects, Topics, Questions, Assessments)...")
    
    for sub_info in SUBJECT_DATA:
        print(f"   📘 Processing Subject: {sub_info['title']}...")
        topics = []
        all_comps_in_subject = []

        # Create Topics and Competencies (Embedded & Flat)
        for topic_data in sub_info["topics"]:
            competencies = []
            for comp_def in topic_data["comps"]:
                comp_id = str(uuid.uuid4())
                
                # Create Competency Object
                competency = {
                    "id": comp_id,
                    "code": f"C-{random.randint(1000, 9999)}",
                    "description": comp_def["desc"], # Use detailed description
                    "target_bloom_level": comp_def["bloom"], # Use FIXED bloom level from TOS
                    "target_difficulty": random.choice(list(DifficultyLevel)),
                    "allocated_items": 5,
                    "created_at": get_utc_now(),
                }
                
                # Save to 'competencies' collection for easy lookup
                await create("competencies", {"data": competency, "id": comp_id}, doc_id=comp_id)
                
                competencies.append(competency)
                all_comps_in_subject.append(competency)

            topic_id = str(uuid.uuid4())
            topics.append({
                "id": topic_id,
                "title": topic_data["title"],
                "weight_percentage": 33.0,
                "competencies": competencies,
                "lecture_content": random.choice(MODULE_CONTENT_TEMPLATES),
                "created_at": get_utc_now(),
            })
            print(f"      - Topic Created: {topic_data['title']} ({len(competencies)} comps)")

        # Create Subject
        subject_data = {
            "title": sub_info["title"],
            "pqf_level": sub_info["pqf_level"],
            "total_weight_percentage": sub_info["total_weight_percentage"],
            "topics": topics,
            "description": sub_info["description"],
            "is_active": True,
            "created_at": get_utc_now(),
        }
        sub_res = await create("subjects", subject_data)
        subject_id = sub_res["id"]

        # Create Questions based on the Subject Title mapping
        custom_list = CUSTOM_QUESTIONS.get(sub_info["title"], [])
        questions_for_assessment = []
        
        if custom_list and all_comps_in_subject:
            print(f"      - Generating {len(custom_list)} questions for {sub_info['title']}...")
            for item in custom_list:
                target_comp = random.choice(all_comps_in_subject)
                q_id = str(uuid.uuid4())
                
                question_data = {
                    "text": item["text"],
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": item["choices"],
                    "correct_answers": item["correct"],
                    "bloom_taxonomy": item["bloom"], # Use specific bloom
                    "difficulty_level": item["difficulty"],
                    "competency_id": target_comp["id"],
                    "is_verified": True,
                    "created_at": get_utc_now(),
                }
                await create("questions", question_data, doc_id=q_id)
                
                # Add to assessment list
                questions_for_assessment.append({
                    "question_id": q_id,
                    "text": item["text"],
                    "choices": item["choices"],
                    "correct_answers": item["correct"],
                    "bloom_taxonomy": item["bloom"],
                    "competency_id": target_comp["id"],
                    "points": 1
                })

        # Create Diagnostic Assessment
        if questions_for_assessment:
            assessment_data = {
                "title": f"{sub_info['title']} - Diagnostic",
                "type": AssessmentType.DIAGNOSTIC.value,
                "subject_id": subject_id,
                "description": f"Baseline assessment for {sub_info['title']}",
                "questions": questions_for_assessment,
                "total_items": len(questions_for_assessment),
                "is_verified": True,
                "created_at": get_utc_now(),
            }
            ass_res = await create("assessments", assessment_data)
            print(f"      - Assessment Created: {assessment_data['title']}")
            
            # Generate Student Submissions
            if student_ids:
                await generate_submissions(student_ids, ass_res["id"], assessment_data)
                print(f"      - Generated submissions for {len(student_ids)} students")

async def generate_submissions(student_ids, assessment_id, assessment_data):
    """Simulates realistic student performance patterns."""
    questions = assessment_data["questions"]
    
    # 80% of students take the assessment
    taking_students = random.sample(student_ids, k=max(1, int(len(student_ids) * 0.8)))

    for uid in taking_students:
        # Assign a random "ability level" to the student (0.0 to 1.0)
        student_ability = random.uniform(0.4, 0.95) 
        
        answers = []
        correct_count = 0

        for q in questions:
            # Probability of correct answer depends on ability vs difficulty (simplified)
            # Higher ability = higher chance
            is_correct = random.random() < student_ability
            
            if is_correct: correct_count += 1
            
            # If incorrect, pick a random wrong answer
            if is_correct:
                ans = q["correct_answers"]
            else:
                wrong_choices = [c for c in q["choices"] if c != q["correct_answers"]]
                ans = random.choice(wrong_choices) if wrong_choices else "Wrong Answer"

            answers.append({
                "question_id": q["question_id"],
                "answer": ans,
                "is_correct": is_correct,
                "competency_id": q["competency_id"],
                "bloom_taxonomy": q["bloom_taxonomy"]
            })

        score = (correct_count / len(questions)) * 100
        
        # Create Submission
        submission = {
            "user_id": uid,
            "assessment_id": assessment_id,
            "subject_id": assessment_data["subject_id"],
            "score": score,
            "total_items": len(questions),
            "answers": answers,
            "submitted_at": get_utc_now() - timedelta(days=random.randint(1, 14)),
            "created_at": get_utc_now(),
        }
        await create("assessment_submissions", submission)

async def main():
    print("🚀 STARTING POPULATION (PSYCHOMETRICIAN TOS)...")
    await reset_database()
    role_ids = await setup_roles()
    student_ids, faculty_ids, credentials = await generate_users(role_ids)
    await generate_content(student_ids, faculty_ids)
    
    print("\n" + "="*70)
    print("🔐  USER CREDENTIALS (COPY THESE TO LOGIN)")
    print("="*70)
    print(f"{'ROLE':<10} | {'EMAIL':<35} | {'PASSWORD'}")
    print("-" * 70)
    
    # Print Admin
    for cred in credentials:
        if cred['role'] == "ADMIN":
            print(f"{cred['role']:<10} | {cred['email']:<35} | {cred['password']}")
            
    print("-" * 70)
    
    # Print Faculty (Limit to 2)
    count = 0
    for cred in credentials:
        if cred['role'] == "FACULTY" and count < 2:
            print(f"{cred['role']:<10} | {cred['email']:<35} | {cred['password']}")
            count += 1
            
    print("-" * 70)
            
    # Print Students (Limit to 3)
    count = 0
    for cred in credentials:
        if cred['role'] == "STUDENT" and count < 3:
            print(f"{cred['role']:<10} | {cred['email']:<35} | {cred['password']}")
            count += 1
            
    print("="*70)
    print("\n✨ POPULATION COMPLETE - READY FOR ANALYTICS")

if __name__ == "__main__":
    asyncio.run(main())