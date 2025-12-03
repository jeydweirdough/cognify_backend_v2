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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Initialize Firebase
from core.firebase import db
from services.crud_services import create, read_query, read_one, delete
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
WHITELIST_COLLECTION = "whitelist"

# --- DATA DEFINITIONS ---

ROLE_MAP = {"admin": "admin", "student": "student", "faculty": "faculty_member"}

# Curriculum Data (Subject -> Topics -> Competencies)
SUBJECT_DATA = [
    {
        "title": "Developmental Psychology",
        "description": "Study of human growth and changes from childhood to adulthood.",
        "pqf_level": 6,
        "topics": [
            {
                "title": "Nature vs Nurture",
                "comps": [
                    "Analyze genetic influences",
                    "Evaluate environmental factors",
                ],
            },
            {
                "title": "Research Methods",
                "comps": [
                    "Compare longitudinal vs cross-sectional",
                    "Design developmental studies",
                ],
            },
            {
                "title": "Piaget's Stages",
                "comps": [
                    "Differentiate sensorimotor and preoperational",
                    "Apply concrete operational concepts",
                ],
            },
        ],
    },
    {
        "title": "Industrial-Organizational Psychology",
        "description": "Study of human behavior in the workplace, applying psychological principles to human management",
        "pqf_level": 6,
        "topics": [
            {
                "title": "Job Analysis and Personnel Selection",
                "comps": [
                    "Conduct job analysis using interviews, observation, and task inventories",
                    "Develop valid and reliable employee selection tools",
                    "Differentiate between structured and unstructured interviews",
                ],
            },
            {
                "title": "Training and Development",
                "comps": [
                    "Design evidence-based training programs",
                    "Apply learning theories to employee training",
                    "Evaluate training effectiveness using Kirkpatrick’s model",
                ],
            },
            {
                "title": "Work Motivation and Job Satisfaction",
                "comps": [
                    "Apply motivation theories (Maslow, Herzberg, Vroom’s Expectancy Theory)",
                    "Assess factors influencing job satisfaction",
                    "Analyze the relationship between motivation, performance, and productivity",
                ],
            },
        ],
    },
    {
        "title": "Abnormal Psychology",
        "description": "Study of psychological disorders, their causes, and treatments.",
        "pqf_level": 6,
        "topics": [
            {
                "title": "Anxiety Disorders",
                "comps": ["Identify symptoms of GAD", "Differentiate phobias"],
            },
            {
                "title": "DSM-5 Criteria",
                "comps": ["Apply diagnostic criteria", "Evaluate comorbidity"],
            },
            {
                "title": "Personality Disorders",
                "comps": ["Analyze Cluster B traits", "Critique treatment approaches"],
            },
        ],
    },
    {
        "title": "Psychological Assessment",
        "description": "Understanding and using psychological tests.",
        "pqf_level": 6,
        "topics": [
            {
                "title": "Psychometrics",
                "comps": [
                    "Calculate standard deviation",
                    "Interpret normal distribution",
                ],
            },
            {
                "title": "Validity & Reliability",
                "comps": [
                    "Differentiate content and construct validity",
                    "Assess test-retest reliability",
                ],
            },
            {
                "title": "IQ Testing",
                "comps": [
                    "Interpret WAIS-IV scores",
                    "Analyze cultural bias in testing",
                ],
            },
        ],
    },
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
            email_verified=True,
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
        return existing[0]["id"]

    entry = {
        "email": email,
        "assigned_role": role,
        "is_registered": True,  # Auto-mark as registered since we are seeding
        "added_by": adder_id,
        "created_at": get_utc_now(),
    }
    res = await create(WHITELIST_COLLECTION, entry)
    return res["id"]


async def generate_users(role_ids):
    print("\n👥 Generating Users & Whitelist...")
    faculty_ids = []
    student_ids = []

    # 1. Admin
    admin_email = f"{TEST_PREFIX}admin@cvsu.edu.ph"
    uid = await create_auth_user(admin_email, "admin")
    if uid:
        await create(
            USER_COLLECTION,
            {
                "email": admin_email,
                "first_name": "System",
                "last_name": "Admin",
                "user_name": "sysadmin",
                "role_id": role_ids["admin"],
                "is_verified": True,
                "is_registered": True,
                "is_active": True,
                "created_at": get_utc_now(),
            },
            doc_id=uid,
        )
        await create_whitelist_entry(admin_email, UserRole.ADMIN, uid)

    # 2. Faculty
    for i in range(NUM_FACULTY):
        email = f"{TEST_PREFIX}faculty_{i}@cvsu.edu.ph"
        uid = await create_auth_user(email, "faculty")
        if uid:
            await create(
                USER_COLLECTION,
                {
                    "email": email,
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "user_name": f"faculty_{i}",
                    "role_id": role_ids["faculty"],
                    "is_verified": True,
                    "is_registered": True,
                    "is_active": True,
                    "created_at": get_utc_now(),
                },
                doc_id=uid,
            )
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
                    "interruption_frequency": "Low",
                },
                "progress_report": [],
            }
            await create(
                USER_COLLECTION,
                {
                    "email": email,
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "user_name": f"student_{i}",
                    "role_id": role_ids["student"],
                    "is_verified": True,
                    "is_registered": True,
                    "is_active": True,
                    "student_info": student_info,
                    "created_at": get_utc_now(),
                },
                doc_id=uid,
            )
            student_ids.append(uid)
            await create_whitelist_entry(email, UserRole.STUDENT, "system")

    print(
        f"   ✅ Created: {len(student_ids)} Students, {len(faculty_ids)} Faculty, 1 Admin"
    )
    return student_ids, faculty_ids


async def reset_database():
    print("\n🧹 Resetting Database...")
    collections = [
        "roles",
        USER_COLLECTION,
        WHITELIST_COLLECTION,
        "subjects",
        "modules",
        "assessments",
        "assessment_submissions",
        "study_logs",
    ]
    for name in collections:
        try:
            col_ref = db.collection(name)
            docs = list(col_ref.list_documents())
            if not docs:
                print(f"   - {name}: 0 deleted")
                continue
            batch = db.batch()
            for doc_ref in docs:
                batch.delete(doc_ref)
            batch.commit()
            print(f"   - {name}: {len(docs)} deleted")
        except Exception as e:
            print(f"   ⚠️ {name} reset failed: {e}")
    try:
        count = 0
        for user_record in auth.list_users().iterate_all():
            email = getattr(user_record, "email", None)
            if email and email.startswith(TEST_PREFIX):
                try:
                    auth.delete_user(user_record.uid)
                    count += 1
                except Exception:
                    pass
        print(f"   - Auth users deleted: {count}")
    except Exception as e:
        print(f"   ⚠️ Auth cleanup skipped: {e}")


async def generate_content(student_ids, faculty_ids):
    print("\n📚 Generating Content (Subjects, Modules, Assessments)...")
    created_subjects = []
    total_modules = 0
    total_assessments = 0

    CUSTOM_QUESTIONS = {
        "Developmental Psychology": [
            {
                "text": "Which of the following best describes Erikson’s stage of identity vs. role confusion?",
                "choices": [
                    "A. Developing trust in caregivers",
                    "B. Exploring personal values and beliefs",
                    "C. Learning basic motor skills",
                    "D. Coping with generativity vs. stagnation",
                ],
                "correct": "B",
            },
            {
                "text": "Piaget’s concrete operational stage is characterized by:",
                "choices": [
                    "A. Symbolic thinking and egocentrism",
                    "B. Abstract reasoning and hypotheticals",
                    "C. Logical thinking about concrete objects",
                    "D. Sensorimotor exploration",
                ],
                "correct": "C",
            },
            {
                "text": "Which of the following is an example of a psychosocial milestone in adolescence?",
                "choices": [
                    "A. Developing object permanence",
                    "B. Forming intimate peer relationships",
                    "C. Achieving industry in schoolwork",
                    "D. Basic trust in caregivers",
                ],
                "correct": "B",
            },
            {
                "text": "Vygotsky emphasized the importance of:",
                "choices": [
                    "A. Biological maturation",
                    "B. Social interaction in cognitive development",
                    "C. Reinforcement and punishment",
                    "D. Observational learning alone",
                ],
                "correct": "B",
            },
            {
                "text": "The attachment theory by Bowlby highlights:",
                "choices": [
                    "A. The role of punishment in shaping behavior",
                    "B. The secure emotional bond between child and caregiver",
                    "C. The stages of moral reasoning",
                    "D. Cognitive schemas in learning",
                ],
                "correct": "B",
            },
        ],
        "Industrial-Organizational Psychology": [
            {
                "text": "Which of the following best describes the purpose of job analysis?",
                "choices": [
                    "A. To evaluate employees’ personal values",
                    "B. To identify the duties, responsibilities, and skills required for a job",
                    "C. To study workplace morale and job satisfaction",
                    "D. To determine an organization’s financial goals",
                ],
                "correct": "B",
            },
            {
                "text": "What is the primary goal of performance appraisal in I/O psychology?",
                "choices": [
                    "A. To assign salaries randomly",
                    "B. To assess and improve employee job performance",
                    "C. To train employees in basic motor skills",
                    "D. To evaluate personal life satisfaction",
                ],
                "correct": "B",
            },
            {
                "text": "Which concept refers to an employee's perception of fairness in organizational procedures and decision-making?",
                "choices": [
                    "A. Job enrichment",
                    "B. Organizational justice",
                    "C. Social facilitation",
                    "D. Maslow’s hierarchy of needs",
                ],
                "correct": "B",
            },
            {
                "text": "What is the main focus of work motivation theories in I/O psychology?",
                "choices": [
                    "A. Understanding cognitive development",
                    "B. Explaining what drives employees to perform and stay engaged",
                    "C. Analyzing market trends for business growth",
                    "D. Designing ergonomic office furniture",
                ],
                "correct": "B",
            },
            {
                "text": "Which of the following is an example of an I/O psychologist's role?",
                "choices": [
                    "A. Conducting therapy sessions for depression",
                    "B. Developing recruitment strategies and selection procedures",
                    "C. Teaching high school psychology classes",
                    "D. Conducting experiments on infant attachment",
                ],
                "correct": "B",
            },
        ],
        "Abnormal Psychology": [
            {
                "text": "Which of the following is classified as a mood disorder?",
                "choices": [
                    "A. Schizophrenia",
                    "B. Bipolar disorder",
                    "C. Obsessive-compulsive disorder",
                    "D. Panic disorder",
                ],
                "correct": "B",
            },
            {
                "text": "The main feature of schizophrenia is:",
                "choices": [
                    "A. Excessive worry",
                    "B. Delusions and hallucinations",
                    "C. Recurrent panic attacks",
                    "D. Impulsivity and hyperactivity",
                ],
                "correct": "B",
            },
            {
                "text": "Generalized Anxiety Disorder (GAD) is characterized by:",
                "choices": [
                    "A. Persistent and excessive worry for at least 6 months",
                    "B. Delusions and hallucinations",
                    "C. Recurrent episodes of mania",
                    "D. Impulsive aggression",
                ],
                "correct": "A",
            },
            {
                "text": "Which of the following is a hallmark of obsessive-compulsive disorder?",
                "choices": [
                    "A. Mood swings",
                    "B. Intrusive thoughts and repetitive behaviors",
                    "C. Paranoia",
                    "D. Dissociation",
                ],
                "correct": "B",
            },
            {
                "text": "Post-Traumatic Stress Disorder (PTSD) may develop after:",
                "choices": [
                    "A. Chronic workplace stress",
                    "B. Experiencing or witnessing a traumatic event",
                    "C. Inadequate parenting",
                    "D. Genetic predisposition alone",
                ],
                "correct": "B",
            },
        ],
        "Psychological Assessment": [
            {
                "text": "Which of the following is the primary purpose of a psychometric test?",
                "choices": [
                    "A. To provide therapy for mental disorders",
                    "B. To measure individual differences in psychological traits",
                    "C. To evaluate physical health",
                    "D. To predict social popularity",
                ],
                "correct": "B",
            },
            {
                "text": "A test that yields consistent results over time is considered:",
                "choices": [
                    "A. Valid",
                    "B. Reliable",
                    "C. Norm-referenced",
                    "D. Subjective",
                ],
                "correct": "B",
            },
            {
                "text": "Which type of validity assesses whether a test appears to measure what it claims?",
                "choices": [
                    "A. Predictive validity",
                    "B. Content validity",
                    "C. Face validity",
                    "D. Construct validity",
                ],
                "correct": "C",
            },
            {
                "text": "Standardization in psychological testing refers to:",
                "choices": [
                    "A. Administering a test uniformly across individuals",
                    "B. Scoring a test based on personal judgment",
                    "C. Allowing flexibility in instructions",
                    "D. Adapting test content per examinee",
                ],
                "correct": "A",
            },
            {
                "text": "Which assessment tool is most suitable for measuring intelligence?",
                "choices": [
                    "A. Rorschach Inkblot Test",
                    "B. Wechsler Adult Intelligence Scale (WAIS)",
                    "C. Beck Depression Inventory",
                    "D. Minnesota Multiphasic Personality Inventory (MMPI)",
                ],
                "correct": "B",
            },
        ],
    }

    for sub_info in SUBJECT_DATA:
        topics = []
        all_comps_in_subject = []

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
                    "allocated_items": 5,
                }
                competencies.append(competency)
                all_comps_in_subject.append(competency)

            topics.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": topic_data["title"],
                    "weight_percentage": 33.0,
                    "competencies": competencies,
                    "lecture_content": "Content placeholder...",
                    "image": None,
                }
            )

        is_subject_verified = random.choice([True, True, False])

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
            "created_at": get_utc_now(),
        }

        sub_res = await create("subjects", subject_data)
        subject_id = sub_res["id"]
        created_subjects.append({"id": subject_id, "data": subject_data})

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
                "created_at": get_utc_now(),
            }
            await create("modules", module_data)
            total_modules += 1

        if not all_comps_in_subject:
            continue

        custom_list = CUSTOM_QUESTIONS.get(sub_info["title"], [])
        if not custom_list:
            continue

        questions = []
        for item in custom_list:
            target_comp = random.choice(all_comps_in_subject)
            questions.append(
                {
                    "question_id": str(uuid.uuid4()),
                    "text": item["text"],
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": item["choices"],
                    "correct": item["correct"],
                    "bloom_taxonomy": BloomTaxonomy.UNDERSTANDING,
                    "difficulty_level": DifficultyLevel.MODERATE,
                    "competency_id": target_comp["id"],
                    "points": 1,
                }
            )

        assessment_data = {
            "title": f"{sub_info['title']} - Diagnostic Assessment",
            "type": AssessmentType.DIAGNOSTIC,
            "subject_id": subject_id,
            "purpose": "Diagnostic",
            "total_items": len(questions),
            "questions": questions,
            "is_verified": True,
            "is_rejected": False,
            "created_by": random.choice(faculty_ids) if faculty_ids else "system",
            "description": "Standard diagnostic test to evaluate readiness across core subjects.",
            "bloom_levels": list(set([q["bloom_taxonomy"] for q in questions])),
            "created_at": get_utc_now(),
        }

        ass_res = await create("assessments", assessment_data)
        total_assessments += 1
        await generate_submissions(student_ids, ass_res["id"], assessment_data)

    print(
        f"   ✅ Created: {len(created_subjects)} Subjects, {total_modules} Modules, {total_assessments} Active Assessments"
    )


async def generate_submissions(student_ids, assessment_id, assessment_data):
    """Simulates students taking the assessment."""
    questions = assessment_data["questions"]

    # Randomly select 70% of students to have taken this assessment
    taking_students = random.sample(student_ids, k=int(len(student_ids) * 0.7))

    for uid in taking_students:
        # Simulate student performance
        ability = random.uniform(0.3, 0.95)  # Student ability 30% to 95%

        answers = []
        correct_count = 0

        for q in questions:
            # Chance to answer correctly based on ability
            is_correct = random.random() < ability
            if is_correct:
                correct_count += 1

            answers.append(
                {
                    "question_id": q["question_id"],
                    "is_correct": is_correct,
                    "competency_id": q["competency_id"],
                    "bloom_taxonomy": q["bloom_taxonomy"],
                }
            )

        score = (correct_count / len(questions)) * 100

        submission = {
            "user_id": uid,
            "assessment_id": assessment_id,
            "subject_id": assessment_data["subject_id"],
            "score": score,
            "total_items": len(questions),
            "time_taken_seconds": random.randint(300, 3600),
            "answers": answers,
            "submitted_at": get_utc_now() - timedelta(days=random.randint(1, 30)),
            "created_at": get_utc_now(),
        }
        await create("assessment_submissions", submission)

        # Also create a study log for this interaction
        await create(
            "study_logs",
            {
                "user_id": uid,
                "resource_id": assessment_id,
                "resource_type": "assessment",
                "start_time": get_utc_now() - timedelta(days=random.randint(1, 30)),
                "duration_seconds": random.randint(300, 3600),
                "completion_status": ProgressStatus.COMPLETED,
                "created_at": get_utc_now(),
            },
        )


async def main():
    print("🚀 STARTING POPULATION")
    print("==================================")
    await reset_database()

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
