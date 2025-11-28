# services/analytics_service.py
from typing import Dict, List, Optional

import numpy as np
from database.enums import BloomTaxonomy
from services.crud_services import read_query, read_one
from services.inference_service import performance_forecaster
from datetime import datetime, timedelta
from fastapi import HTTPException
import statistics
from services.adaptability_service import analyze_study_behavior
from services.inference_service import passing_predictor
from services.inference_service import AIInferenceEngine as ai_engine

async def calculate_passing_rate(subject_id: Optional[str] = None, assessment_id: Optional[str] = None) -> Dict:
    """
    Calculate overall passing rate for assessments.
    Passing score is typically 75% in Philippine education system.
    """
    filters = []
    if subject_id:
        filters.append(("subject_id", "==", subject_id))
    if assessment_id:
        filters.append(("assessment_id", "==", assessment_id))
    
    # Get all assessment submissions
    submissions = await read_query("assessment_submissions", filters)
    
    if not submissions:
        return {
            "total_submissions": 0,
            "passing_count": 0,
            "failing_count": 0,
            "passing_rate": 0.0,
            "average_score": 0.0
        }
    
    passing_threshold = 75.0
    scores = [s["data"].get("score", 0) for s in submissions]
    passing_count = sum(1 for score in scores if score >= passing_threshold)
    failing_count = len(scores) - passing_count
    
    return {
        "total_submissions": len(submissions),
        "passing_count": passing_count,
        "failing_count": failing_count,
        "passing_rate": (passing_count / len(submissions)) * 100,
        "average_score": statistics.mean(scores) if scores else 0.0,
        "median_score": statistics.median(scores) if scores else 0.0,
        "highest_score": max(scores) if scores else 0.0,
        "lowest_score": min(scores) if scores else 0.0
    }


async def predict_student_passing_probability(user_id: str, subject_id: str) -> Dict:
    """
    Use ML model to predict probability of student passing based on behavior and performance.
    """
    # Get student profile
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_info = profile.get("student_info", {})
    
    # Get behavioral data
    study_logs = await read_query("study_logs", [
        ("user_id", "==", user_id),
        ("completion_status", "==", "completed")
    ])
    
    # Get assessment history
    submissions = await read_query("assessment_submissions", [
        ("user_id", "==", user_id),
        ("subject_id", "==", subject_id)
    ])
    
    # Calculate features
    avg_session_length = 0.0
    avg_interruptions = 0.0
    total_study_time = 0.0
    
    if study_logs:
        durations = [log["data"].get("duration_seconds", 0) / 60 for log in study_logs]
        interruptions = [log["data"].get("interruptions_count", 0) for log in study_logs]
        
        avg_session_length = statistics.mean(durations) if durations else 0.0
        avg_interruptions = statistics.mean(interruptions) if interruptions else 0.0
        total_study_time = sum(durations)
    
    # Calculate average score
    avg_score = 0.0
    if submissions:
        scores = [s["data"].get("score", 0) for s in submissions]
        avg_score = statistics.mean(scores) if scores else 0.0
    
    # Get completion rates
    progress_reports = student_info.get("progress_report", [])
    avg_completion = 0.0
    if progress_reports:
        completions = [pr.get("overall_completeness", 0) for pr in progress_reports]
        avg_completion = statistics.mean(completions) if completions else 0.0
    
    # Prepare features for ML model
    features = [
        avg_score,                          # Historical performance
        avg_completion,                     # Progress completion rate
        student_info.get("timeliness", 0),  # Timeliness score
        avg_session_length,                 # Study behavior
        avg_interruptions,                  # Focus indicator
        total_study_time,                   # Total engagement
        len(submissions)                    # Assessment attempts
    ]
    
    try:
        # Run ML prediction
        prediction = performance_forecaster.predict(features)
        probability = float(prediction[0][0])  # Probability of passing
        
        # Determine risk level
        if probability >= 0.8:
            risk_level = "Low Risk"
            recommendation = "Student is on track to pass"
        elif probability >= 0.6:
            risk_level = "Moderate Risk"
            recommendation = "Student needs moderate support"
        else:
            risk_level = "High Risk"
            recommendation = "Student needs immediate intervention"
        
        return {
            "user_id": user_id,
            "subject_id": subject_id,
            "passing_probability": probability,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "contributing_factors": {
                "average_score": avg_score,
                "completion_rate": avg_completion,
                "study_behavior": "Good" if avg_interruptions < 3 else "Needs Improvement",
                "total_study_time_hours": total_study_time / 60
            }
        }
        
    except FileNotFoundError:
        # Fallback if model not available
        simple_probability = avg_score / 100.0
        return {
            "user_id": user_id,
            "subject_id": subject_id,
            "passing_probability": simple_probability,
            "risk_level": "Unknown (Model not available)",
            "recommendation": "Manual assessment recommended",
            "note": "Using simple heuristic - ML model not loaded"
        }


async def analyze_student_weaknesses(user_id: str, subject_id: str) -> Dict:
    """
    Identify student's weak competencies and recommend study materials.
    """
    # Get assessment submissions
    submissions = await read_query("assessment_submissions", [
        ("user_id", "==", user_id),
        ("subject_id", "==", subject_id)
    ])
    
    if not submissions:
        return {
            "weaknesses": [],
            "recommendations": [],
            "message": "No assessment data available"
        }
    
    # Analyze performance by competency
    competency_scores = {}
    
    for submission in submissions:
        answers = submission["data"].get("answers", [])
        for answer in answers:
            comp_id = answer.get("competency_id")
            is_correct = answer.get("is_correct", False)
            
            if comp_id:
                if comp_id not in competency_scores:
                    competency_scores[comp_id] = {"correct": 0, "total": 0}
                
                competency_scores[comp_id]["total"] += 1
                if is_correct:
                    competency_scores[comp_id]["correct"] += 1
    
    # Calculate mastery percentages
    weaknesses = []
    for comp_id, stats in competency_scores.items():
        mastery = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        
        if mastery < 60:  # Below 60% is considered weak
            weaknesses.append({
                "competency_id": comp_id,
                "mastery_percentage": mastery,
                "correct_answers": stats["correct"],
                "total_attempts": stats["total"]
            })
    
    # Sort by weakest
    weaknesses.sort(key=lambda x: x["mastery_percentage"])
    
    # Get recommended modules
    recommendations = await recommend_study_modules(user_id, subject_id, weaknesses)
    
    return {
        "user_id": user_id,
        "subject_id": subject_id,
        "weaknesses": weaknesses[:5],  # Top 5 weakest
        "recommendations": recommendations,
        "total_competencies_assessed": len(competency_scores)
    }


async def recommend_study_modules(user_id: str, subject_id: str, weaknesses: List[Dict]) -> List[Dict]:
    """
    Recommend study modules based on student's weaknesses and learning behavior.
    """
    if not weaknesses:
        return []
    
    # Get student behavior profile
    profile = await read_one("user_profiles", user_id)
    behavior_profile = profile.get("student_info", {}).get("behavior_profile", {})
    
    # Get subject topics
    subject = await read_one("subjects", subject_id)
    if not subject:
        return []
    
    recommendations = []
    weak_competency_ids = [w["competency_id"] for w in weaknesses]
    
    # Find topics containing weak competencies
    for topic in subject.get("topics", []):
        for competency in topic.get("competencies", []):
            if competency["id"] in weak_competency_ids:
                # Check if topic has study material
                if topic.get("lecture_content"):
                    # Calculate recommendation priority
                    weakness_severity = next(
                        (w["mastery_percentage"] for w in weaknesses if w["competency_id"] == competency["id"]),
                        50
                    )
                    
                    priority = 100 - weakness_severity  # Lower mastery = higher priority
                    
                    recommendations.append({
                        "topic_id": topic["id"],
                        "topic_title": topic["title"],
                        "competency_code": competency["code"],
                        "competency_description": competency["description"],
                        "priority": priority,
                        "estimated_study_time": calculate_estimated_time(behavior_profile, topic),
                        "module_url": topic.get("lecture_content")
                    })
                    break  # Only add topic once
    
    # Sort by priority
    recommendations.sort(key=lambda x: x["priority"], reverse=True)
    
    return recommendations[:10]  # Return top 10


def calculate_estimated_time(behavior_profile: Dict, topic: Dict) -> str:
    """
    Estimate study time based on student's learning pace.
    """
    base_time = 60  # minutes
    
    pace = behavior_profile.get("learning_pace", "Standard")
    
    if pace == "Fast":
        estimated = base_time * 0.7
    elif pace == "Slow":
        estimated = base_time * 1.3
    else:
        estimated = base_time
    
    hours = int(estimated // 60)
    minutes = int(estimated % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


async def get_subject_analytics(subject_id: str) -> Dict:
    """
    Comprehensive analytics for a subject.
    """
    # Get all students enrolled
    students = await read_query("user_profiles", [])
    student_ids = [s["id"] for s in students if s["data"].get("role_id") == "student"]
    
    # Get passing rates
    passing_data = await calculate_passing_rate(subject_id=subject_id)
    
    # Get average completion rates
    total_completion = 0
    completion_count = 0
    
    for student_id in student_ids:
        profile = await read_one("user_profiles", student_id)
        if profile:
            progress_reports = profile.get("student_info", {}).get("progress_report", [])
            for report in progress_reports:
                if report.get("subject_id") == subject_id:
                    total_completion += report.get("overall_completeness", 0)
                    completion_count += 1
    
    avg_completion = (total_completion / completion_count) if completion_count > 0 else 0
    
    # Get most difficult topics
    topic_difficulties = await analyze_topic_difficulty(subject_id)
    
    return {
        "subject_id": subject_id,
        "passing_statistics": passing_data,
        "average_completion_rate": avg_completion,
        "total_students": len(student_ids),
        "difficult_topics": topic_difficulties[:5],
        "engagement_metrics": await get_engagement_metrics(subject_id)
    }


async def analyze_topic_difficulty(subject_id: str) -> List[Dict]:
    """
    Identify which topics students struggle with most.
    """
    submissions = await read_query("assessment_submissions", [
        ("subject_id", "==", subject_id)
    ])
    
    topic_performance = {}
    
    for submission in submissions:
        answers = submission["data"].get("answers", [])
        for answer in answers:
            topic_id = answer.get("topic_id")
            is_correct = answer.get("is_correct", False)
            
            if topic_id:
                if topic_id not in topic_performance:
                    topic_performance[topic_id] = {"correct": 0, "total": 0}
                
                topic_performance[topic_id]["total"] += 1
                if is_correct:
                    topic_performance[topic_id]["correct"] += 1
    
    difficulties = []
    for topic_id, stats in topic_performance.items():
        success_rate = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        difficulty_score = 100 - success_rate
        
        difficulties.append({
            "topic_id": topic_id,
            "difficulty_score": difficulty_score,
            "success_rate": success_rate,
            "attempts": stats["total"]
        })
    
    difficulties.sort(key=lambda x: x["difficulty_score"], reverse=True)
    return difficulties


async def get_engagement_metrics(subject_id: str) -> Dict:
    """
    Calculate student engagement metrics for a subject.
    """
    study_logs = await read_query("study_logs", [
        ("resource_type", "==", "module")
    ])
    
    total_sessions = len(study_logs)
    total_time = sum(log["data"].get("duration_seconds", 0) for log in study_logs) / 3600
    avg_interruptions = statistics.mean([log["data"].get("interruptions_count", 0) for log in study_logs]) if study_logs else 0
    
    return {
        "total_study_sessions": total_sessions,
        "total_study_hours": round(total_time, 2),
        "average_session_length_minutes": round((total_time * 60) / total_sessions, 2) if total_sessions > 0 else 0,
        "average_interruptions_per_session": round(avg_interruptions, 2),
        "engagement_quality": "High" if avg_interruptions < 2 else "Medium" if avg_interruptions < 5 else "Low"
    }

async def get_global_predictions() -> Dict:
    """
    Aggregates data for the MAIN Admin Dashboard.
    Robustly calculates Bloom stats by normalizing keys.
    """
    # 1. Fetch All Data
    all_users = await read_query("user_profiles", [])
    submissions = await read_query("assessment_submissions", [])
    all_subjects = await read_query("subjects", [])
    all_assessments = await read_query("assessments", [])

    # 2. Mappings
    subject_map = {s["id"]: s["data"].get("title", "Unknown Subject") for s in all_subjects}
    
    # Map Assessment -> Questions -> Bloom Level
    assessment_bloom_map = {}
    for a in all_assessments:
        q_data = {}
        for q in a["data"].get("questions", []):
            # [FIX] Robust extraction of Bloom Taxonomy
            raw_bloom = q.get("bloom_taxonomy", "remembering")
            # Handle Enum objects, strings, or mixed case
            if hasattr(raw_bloom, "value"):
                bloom_val = str(raw_bloom.value).lower()
            else:
                bloom_val = str(raw_bloom).lower()
            
            q_data[q["id"]] = bloom_val
        assessment_bloom_map[a["id"]] = q_data

    # 3. Aggregators
    pass_count = 0
    fail_count = 0
    student_scores = {} 
    subject_stats = {}  
    
    # Initialize Bloom Stats with lowercase keys
    # e.g., {'remembering': {total:0, correct:0}, ...}
    bloom_stats = {b.value.lower(): {"total": 0, "correct": 0} for b in BloomTaxonomy}

    # 4. Process Submissions
    for sub in submissions:
        data = sub["data"]
        uid = data.get("user_id")
        score = data.get("score", 0)
        sid = data.get("subject_id")
        aid = data.get("assessment_id")
        answers = data.get("answers", [])

        # Score & Subject Aggregation (Existing working logic)
        if uid not in student_scores: student_scores[uid] = []
        student_scores[uid].append(score)

        if sid:
            if sid not in subject_stats: subject_stats[sid] = {"total": 0, "count": 0}
            subject_stats[sid]["total"] += score
            subject_stats[sid]["count"] += 1

        # Bloom Aggregation
        q_lookup = assessment_bloom_map.get(aid, {})
        
        for ans in answers:
            qid = ans.get("question_id")
            is_correct = ans.get("is_correct", False)
            
            # [FIX] Safe lookup
            bloom = q_lookup.get(qid)
            
            if bloom and bloom in bloom_stats:
                bloom_stats[bloom]["total"] += 1
                if is_correct: 
                    bloom_stats[bloom]["correct"] += 1

    # 5. Format Output
    
    # Predictions List
    predictions = []
    for uid, scores in student_scores.items():
        avg = statistics.mean(scores)
        is_passing = avg >= 75
        if is_passing: pass_count += 1
        else: fail_count += 1
        
        user = next((u for u in all_users if u["id"] == uid), {})
        udata = user.get("data", {})
        
        predictions.append({
            "student_id": uid,
            "first_name": udata.get("first_name"),
            "last_name": udata.get("last_name"),
            "predicted_to_pass": is_passing,
            "overall_score": round(avg, 1),
            "risk_level": "Low" if is_passing else "High",
            "passing_probability": round(avg/100, 2)
        })

    # Core Subjects List
    global_subjects = []
    for sid, stats in subject_stats.items():
        if stats["count"] > 0:
            avg_score = stats["total"] / stats["count"]
            global_subjects.append({
                "subject_id": sid,
                "title": subject_map.get(sid, "General"),
                "passing_rate": round(avg_score, 1)
            })
    global_subjects.sort(key=lambda x: x["passing_rate"])
    
    # Bloom Performance Dict
    global_bloom = {}
    for level, stats in bloom_stats.items():
        if stats["total"] > 0:
            global_bloom[level] = round((stats["correct"] / stats["total"]) * 100, 1)
        else:
            global_bloom[level] = 0

    return {
        "summary": {
            "total_students_predicted": len(student_scores),
            "count_predicted_to_pass": pass_count,
            "count_predicted_to_fail": fail_count,
            "predicted_pass_rate": round((pass_count/len(student_scores)*100), 1) if student_scores else 0
        },
        "predictions": predictions,
        "subjects": global_subjects,       
        "performance_by_bloom": global_bloom # Returns populated stats now
    }


async def get_student_comprehensive_report(user_id: str) -> Dict:
    """
    Generate a full analytics report including Subject-Specific Performance.
    """
    # 1. Verify Student
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")

    student_info = profile.get("student_info", {})

    # 2. Get Data
    submissions = await read_query("assessment_submissions", [("user_id", "==", user_id)])
    # Fetch all subjects to map IDs to Titles
    all_subjects = await read_query("subjects", [])
    subject_map = {s["id"]: s["data"].get("title", "Unknown Subject") for s in all_subjects}

    # 3. Calculate Overall Metrics
    scores = [s["data"].get("score", 0) for s in submissions]
    avg_score = statistics.mean(scores) if scores else 0.0
    
    # --- NEW: Calculate Per-Subject Performance ---
    subject_stats = {}
    for sub in submissions:
        sid = sub["data"].get("subject_id")
        score = sub["data"].get("score", 0)
        
        if sid not in subject_stats:
            subject_stats[sid] = {"total_score": 0, "count": 0}
        
        subject_stats[sid]["total_score"] += score
        subject_stats[sid]["count"] += 1
    
    subject_performance = []
    for sid, stats in subject_stats.items():
        avg = stats["total_score"] / stats["count"]
        subject_performance.append({
            "subject_id": sid,
            "subject_title": subject_map.get(sid, "General Education"), # Fallback name
            "average_score": round(avg, 2),
            "assessments_taken": stats["count"],
            "status": "Needs Review" if avg < 75 else "Good Standing"
        })
    
    # Sort by score ascending (Weakest first)
    subject_performance.sort(key=lambda x: x["average_score"])

    # 4. Generate AI Prediction (Simplified/Robust Version)
    # This uses the available metrics without crashing if features are missing
    probability = 0.0
    risk_level = "Unknown"
    recommendation = "No data available."

    if submissions:
        # Simple heuristic or AI call
        probability = min(1.0, avg_score / 100.0)
        
        # Boost if consistent
        if len(submissions) > 5: probability += 0.05
        
        if probability >= 0.75:
            risk_level = "Low Risk"
            recommendation = "Maintain current study habits."
        elif probability >= 0.60:
            risk_level = "Moderate Risk"
            recommendation = "Focus on the subjects highlighted in 'Needs Review'."
        else:
            risk_level = "High Risk"
            recommendation = "Urgent: Complete diagnostic tests for core subjects."

    # 5. Identify Competency Weaknesses
    competency_scores = {}
    for sub in submissions:
        answers = sub["data"].get("answers", [])
        for ans in answers:
            cid = ans.get("competency_id")
            if cid:
                if cid not in competency_scores: competency_scores[cid] = {"correct": 0, "total": 0}
                competency_scores[cid]["total"] += 1
                if ans.get("is_correct"): competency_scores[cid]["correct"] += 1
    
    weaknesses = []
    for cid, stats in competency_scores.items():
        mastery = (stats["correct"] / stats["total"]) * 100
        if mastery < 75: 
            weaknesses.append({
                "competency_id": cid,
                "mastery": round(mastery, 1),
                "attempts": stats["total"]
            })
    weaknesses.sort(key=lambda x: x["mastery"])

    return {
        "student_profile": {
            "name": f"{profile.get('first_name', '')} {profile.get('last_name', '')}",
            "email": profile.get("email"),
            "id": user_id
        },
        "overall_performance": {
            "average_score": round(avg_score, 2),
            "total_assessments": len(submissions),
            "passing_probability": round(probability * 100, 2), # Return as percentage
            "risk_level": risk_level,
            "recommendation": recommendation
        },
        "subject_performance": subject_performance, # <--- NEW FIELD
        "weaknesses": weaknesses[:5],
        "recent_activity": submissions[-5:] 
    }

def get_avg_completion(student_info: Dict) -> float:
    reports = student_info.get("progress_report", [])
    if not reports: return 0.0
    return sum(r.get("overall_completeness", 0) for r in reports) / len(reports)