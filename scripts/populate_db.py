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
                    "Evaluate training effectiveness using Kirkpatrick's model",
                ],
            },
            {
                "title": "Work Motivation and Job Satisfaction",
                "comps": [
                    "Apply motivation theories (Maslow, Herzberg, Vroom's Expectancy Theory)",
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

# Generic module content templates
MODULE_CONTENT_TEMPLATES = [
    "This module covers the fundamental concepts and theories related to the subject matter. Students will learn about key principles, historical context, and practical applications.",
    "In this section, we explore the main ideas and methodologies used in the field. This module provides a comprehensive overview of the most important research findings and best practices.",
    "This learning material introduces students to essential concepts, definitions, and frameworks. Through case studies and practical examples, students will understand real-world applications.",
    "This module presents a detailed analysis of the core competencies required for mastery. It includes theoretical foundations, practical examples, and assessment strategies.",
    "Students will engage with key theories, research evidence, and practical strategies in this module. The content emphasizes critical thinking and application of concepts.",
]

# Sample questions for each subject
CUSTOM_QUESTIONS = {
    "Developmental Psychology": [
        {
            "text": "Which of the following best describes Erikson's stage of identity vs. role confusion?",
            "choices": [
                "Developing trust in caregivers",
                "Exploring personal values and beliefs",
                "Learning basic motor skills",
                "Coping with generativity vs. stagnation",
            ],
            "correct": "Exploring personal values and beliefs",
            "bloom": "understanding",
            "difficulty": "Moderate",
        },
        {
            "text": "Piaget's concrete operational stage is characterized by:",
            "choices": [
                "Symbolic thinking and egocentrism",
                "Abstract reasoning and hypotheticals",
                "Logical thinking about concrete objects",
                "Sensorimotor exploration",
            ],
            "correct": "Logical thinking about concrete objects",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
        {
            "text": "Which of the following is an example of a psychosocial milestone in adolescence?",
            "choices": [
                "Developing object permanence",
                "Forming intimate peer relationships",
                "Achieving industry in schoolwork",
                "Basic trust in caregivers",
            ],
            "correct": "Forming intimate peer relationships",
            "bloom": "applying",
            "difficulty": "Moderate",
        },
        {
            "text": "Vygotsky emphasized the importance of:",
            "choices": [
                "Biological maturation",
                "Social interaction in cognitive development",
                "Reinforcement and punishment",
                "Observational learning alone",
            ],
            "correct": "Social interaction in cognitive development",
            "bloom": "understanding",
            "difficulty": "Moderate",
        },
        {
            "text": "The attachment theory by Bowlby highlights:",
            "choices": [
                "The role of punishment in shaping behavior",
                "The secure emotional bond between child and caregiver",
                "The stages of moral reasoning",
                "Cognitive schemas in learning",
            ],
            "correct": "The secure emotional bond between child and caregiver",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
    ],
    "Industrial-Organizational Psychology": [
        {
            "text": "Which of the following best describes the purpose of job analysis?",
            "choices": [
                "To evaluate employees' personal values",
                "To identify the duties, responsibilities, and skills required for a job",
                "To study workplace morale and job satisfaction",
                "To determine an organization's financial goals",
            ],
            "correct": "To identify the duties, responsibilities, and skills required for a job",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
        {
            "text": "What is the primary goal of performance appraisal in I/O psychology?",
            "choices": [
                "To assign salaries randomly",
                "To assess and improve employee job performance",
                "To train employees in basic motor skills",
                "To evaluate personal life satisfaction",
            ],
            "correct": "To assess and improve employee job performance",
            "bloom": "understanding",
            "difficulty": "Moderate",
        },
        {
            "text": "Which concept refers to an employee's perception of fairness in organizational procedures?",
            "choices": [
                "Job enrichment",
                "Organizational justice",
                "Social facilitation",
                "Maslow's hierarchy of needs",
            ],
            "correct": "Organizational justice",
            "bloom": "applying",
            "difficulty": "Moderate",
        },
        {
            "text": "What is the main focus of work motivation theories in I/O psychology?",
            "choices": [
                "Understanding cognitive development",
                "Explaining what drives employees to perform and stay engaged",
                "Analyzing market trends for business growth",
                "Designing ergonomic office furniture",
            ],
            "correct": "Explaining what drives employees to perform and stay engaged",
            "bloom": "understanding",
            "difficulty": "Easy",
        },
        {
            "text": "Which of the following is an example of an I/O psychologist's role?",
            "choices": [
                "Conducting therapy sessions for depression",
                "Developing recruitment strategies and selection procedures",
                "Teaching high school psychology classes",
                "Conducting experiments on infant attachment",
            ],
            "correct": "Developing recruitment strategies and selection procedures",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
    ],
    "Abnormal Psychology": [
        {
            "text": "Which of the following is classified as a mood disorder?",
            "choices": [
                "Schizophrenia",
                "Bipolar disorder",
                "Obsessive-compulsive disorder",
                "Panic disorder",
            ],
            "correct": "Bipolar disorder",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
        {
            "text": "The main feature of schizophrenia is:",
            "choices": [
                "Excessive worry",
                "Delusions and hallucinations",
                "Recurrent panic attacks",
                "Impulsivity and hyperactivity",
            ],
            "correct": "Delusions and hallucinations",
            "bloom": "understanding",
            "difficulty": "Moderate",
        },
        {
            "text": "Generalized Anxiety Disorder (GAD) is characterized by:",
            "choices": [
                "Persistent and excessive worry for at least 6 months",
                "Delusions and hallucinations",
                "Recurrent episodes of mania",
                "Impulsive aggression",
            ],
            "correct": "Persistent and excessive worry for at least 6 months",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
        {
            "text": "Which of the following is a hallmark of obsessive-compulsive disorder?",
            "choices": [
                "Mood swings",
                "Intrusive thoughts and repetitive behaviors",
                "Paranoia",
                "Dissociation",
            ],
            "correct": "Intrusive thoughts and repetitive behaviors",
            "bloom": "applying",
            "difficulty": "Moderate",
        },
        {
            "text": "Post-Traumatic Stress Disorder (PTSD) may develop after:",
            "choices": [
                "Chronic workplace stress",
                "Experiencing or witnessing a traumatic event",
                "Inadequate parenting",
                "Genetic predisposition alone",
            ],
            "correct": "Experiencing or witnessing a traumatic event",
            "bloom": "understanding",
            "difficulty": "Easy",
        },
    ],
    "Psychological Assessment": [
        {
            "text": "Which of the following is the primary purpose of a psychometric test?",
            "choices": [
                "To provide therapy for mental disorders",
                "To measure individual differences in psychological traits",
                "To evaluate physical health",
                "To predict social popularity",
            ],
            "correct": "To measure individual differences in psychological traits",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
        {
            "text": "A test that yields consistent results over time is considered:",
            "choices": [
                "Valid",
                "Reliable",
                "Norm-referenced",
                "Subjective",
            ],
            "correct": "Reliable",
            "bloom": "understanding",
            "difficulty": "Moderate",
        },
        {
            "text": "Which type of validity assesses whether a test appears to measure what it claims?",
            "choices": [
                "Predictive validity",
                "Content validity",
                "Face validity",
                "Construct validity",
            ],
            "correct": "Face validity",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
        {
            "text": "Standardization in psychological testing refers to:",
            "choices": [
                "Administering a test uniformly across individuals",
                "Scoring a test based on personal judgment",
                "Allowing flexibility in instructions",
                "Adapting test content per examinee",
            ],
            "correct": "Administering a test uniformly across individuals",
            "bloom": "applying",
            "difficulty": "Moderate",
        },
        {
            "text": "Which assessment tool is most suitable for measuring intelligence?",
            "choices": [
                "Rorschach Inkblot Test",
                "Wechsler Adult Intelligence Scale (WAIS)",
                "Beck Depression Inventory",
                "Minnesota Multiphasic Personality Inventory (MMPI)",
            ],
            "correct": "Wechsler Adult Intelligence Scale (WAIS)",
            "bloom": "remembering",
            "difficulty": "Easy",
        },
    ],
}


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
    existing = await read_query("whitelist", [("email", "==", email)])
    if existing:
        return existing[0]["id"]

    entry = {
        "email": email,
        "assigned_role": role,
        "is_registered": True,  # Auto-mark as registered since we are seeding
        "added_by": adder_id,
        "created_at": get_utc_now(),
    }
    res = await create("whitelist", entry)
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
                "username": "sysadmin",
                "role_id": role_ids["admin"],
                "is_verified": True,
                "is_registered": True,
                "is_active": True,
                "created_at": get_utc_now(),
            },
            doc_id=uid,
        )
        await create_whitelist_entry(admin_email, UserRole.ADMIN, uid)
        print(f"   ✅ Created Admin: {admin_email}")

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
                    "username": f"faculty_{i}",
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
            print(f"   ✅ Created Faculty: {email}")

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
                    "average_session_length": 0.0,
                    "preferred_study_time": "Any",
                },
                "progress_report": [],
                "competency_performance": [],
            }
            await create(
                USER_COLLECTION,
                {
                    "email": email,
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "username": f"student_{i}",
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

    print(f"   ✅ Created: {len(student_ids)} Students, {len(faculty_ids)} Faculty, 1 Admin")
    return student_ids, faculty_ids


async def reset_database():
    print("\n🧹 Resetting Database...")
    collections = [
        "roles",
        USER_COLLECTION,
        "whitelist",
        "subjects",
        "modules",
        "assessments",
        "questions",
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
    print("\n📚 Generating Content (Subjects, Topics, Modules, Questions, Assessments)...")
    created_subjects = []
    total_modules = 0
    total_questions = 0
    total_assessments = 0

    for sub_info in SUBJECT_DATA:
        topics = []
        all_comps_in_subject = []

        # Create Topics and Competencies
        for topic_data in sub_info["topics"]:
            competencies = []
            for comp_text in topic_data["comps"]:
                comp_id = str(uuid.uuid4())
                competency = {
                    "id": comp_id,
                    "code": f"C-{random.randint(100, 999)}",
                    "description": comp_text,
                    "target_bloom_level": random.choice(list(BloomTaxonomy)),
                    "target_difficulty": random.choice(list(DifficultyLevel)),
                    "allocated_items": 5,
                    "created_at": get_utc_now(),
                }
                competencies.append(competency)
                all_comps_in_subject.append(competency)

            topic_id = str(uuid.uuid4())
            topics.append(
                {
                    "id": topic_id,
                    "title": topic_data["title"],
                    "weight_percentage": 33.0,
                    "competencies": competencies,
                    "lecture_content": random.choice(MODULE_CONTENT_TEMPLATES),
                    "image": None,
                    "created_at": get_utc_now(),
                }
            )

        is_subject_verified = random.choice([True, True, False])

        subject_data = {
            "title": sub_info["title"],
            "pqf_level": sub_info["pqf_level"],
            "total_weight_percentage": 100.0,
            "topics": topics,
            "description": sub_info["description"],
            "content": "Subject syllabus and overview content.",
            "material_url": None,
            "image_url": None,
            "icon_name": "book",
            "icon_color": "#000000",
            "icon_bg_color": "#ffffff",
            "is_verified": is_subject_verified,
            "is_active": True,
            "deleted": False,
            "created_by": random.choice(faculty_ids) if faculty_ids else "system",
            "created_at": get_utc_now(),
        }

        sub_res = await create("subjects", subject_data)
        subject_id = sub_res["id"]
        created_subjects.append({"id": subject_id, "data": subject_data})

        # Create Modules for this subject
        for _ in range(random.randint(2, 4)):
            is_mod_verified = random.choice([True, True, False])
            module_data = {
                "title": f"{fake.word().capitalize()} Module",
                "subject_id": subject_id,
                "purpose": fake.sentence(),
                "bloom_levels": [random.choice(list(BloomTaxonomy)).value],
                "input_type": "text",
                "content": random.choice(MODULE_CONTENT_TEMPLATES),
                "material_url": None,
                "cover_image_url": None,
                "author": random.choice(faculty_ids) if faculty_ids else "system",
                "is_verified": is_mod_verified,
                "verified_at": get_utc_now() if is_mod_verified else None,
                "verified_by": random.choice(faculty_ids) if is_mod_verified and faculty_ids else None,
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "created_at": get_utc_now(),
            }
            await create("modules", module_data)
            total_modules += 1

        # Create Questions for this subject
        custom_list = CUSTOM_QUESTIONS.get(sub_info["title"], [])
        if custom_list and all_comps_in_subject:
            for item in custom_list:
                target_comp = random.choice(all_comps_in_subject)
                question_data = {
                    "text": item["text"],
                    "type": QuestionType.MULTIPLE_CHOICE,
                    "choices": item["choices"],
                    "correct_answers": item["correct"],
                    "bloom_taxonomy": item["bloom"],
                    "difficulty_level": item["difficulty"],
                    "competency_id": target_comp["id"],
                    "is_verified": random.choice([True, True, False]),
                    "verified_at": get_utc_now(),
                    "verified_by": random.choice(faculty_ids) if faculty_ids else None,
                    "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                    "created_at": get_utc_now(),
                }
                await create("questions", question_data)
                total_questions += 1

        # Create Assessment for this subject
        if custom_list and all_comps_in_subject:
            questions = []
            for item in custom_list:
                target_comp = random.choice(all_comps_in_subject)
                questions.append(
                    {
                        "question_id": str(uuid.uuid4()),
                        "text": item["text"],
                        "type": QuestionType.MULTIPLE_CHOICE,
                        "choices": item["choices"],
                        "correct_answers": item["correct"],
                        "bloom_taxonomy": item["bloom"],
                        "difficulty_level": item["difficulty"],
                        "competency_id": target_comp["id"],
                        "points": 1,
                    }
                )

            assessment_data = {
                "title": f"{sub_info['title']} - Diagnostic Assessment",
                "type": AssessmentType.DIAGNOSTIC.value,
                "subject_id": subject_id,
                "description": f"Standard diagnostic test for {sub_info['title']}",
                "module_id": None,
                "bloom_levels": list(set([q["bloom_taxonomy"] for q in questions])),
                "total_items": len(questions),
                "questions": questions,
                "is_verified": True,
                "is_rejected": False,
                "created_by": random.choice(faculty_ids) if faculty_ids else "system",
                "created_at": get_utc_now(),
            }

            ass_res = await create("assessments", assessment_data)
            total_assessments += 1

            # Generate Student Submissions
            if student_ids:
                await generate_submissions(student_ids, ass_res["id"], assessment_data)

    print(f"   ✅ Created: {len(created_subjects)} Subjects")
    print(f"   ✅ Created: {total_modules} Modules")
    print(f"   ✅ Created: {total_questions} Questions")
    print(f"   ✅ Created: {total_assessments} Assessments")


async def generate_submissions(student_ids, assessment_id, assessment_data):
    """Simulates students taking the assessment."""
    questions = assessment_data["questions"]

    # Randomly select 70% of students to have taken this assessment
    taking_students = random.sample(student_ids, k=max(1, int(len(student_ids) * 0.7)))

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
                    "answer": q["choices"][0] if is_correct else random.choice(q["choices"]),
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
                "end_time": get_utc_now() - timedelta(days=random.randint(0, 30)),
                "duration_seconds": random.randint(300, 3600),
                "interruptions_count": random.randint(0, 5),
                "idle_time_seconds": random.randint(0, 600),
                "completion_status": ProgressStatus.COMPLETED.value,
                "created_at": get_utc_now(),
            },
        )


async def main():
    print("🚀 STARTING COMPREHENSIVE DATABASE POPULATION")
    print("=" * 50)
    await reset_database()

    # 1. Setup Roles
    role_ids = await setup_roles()

    # 2. Create Users (and Whitelist them)
    student_ids, faculty_ids = await generate_users(role_ids)

    # 3. Create Content & Analytics
    await generate_content(student_ids, faculty_ids)

    print("\n" + "=" * 50)
    print("✨ POPULATION COMPLETE")
    print("=" * 50)
    print("\n📊 Summary:")
    print("   ✅ Roles configured")
    print("   ✅ Users created and whitelisted")
    print("   ✅ Curriculum structure (Subjects → Topics → Competencies)")
    print("   ✅ Modules with generic text content")
    print("   ✅ Questions from question bank")
    print("   ✅ Assessments with student submissions")
    print("   ✅ Study logs and analytics data")
    print("\n🎯 Ready for testing!")


if __name__ == "__main__":
    asyncio.run(main())