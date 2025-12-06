# services/analytics_service.py
from typing import Dict, List, Optional
import statistics
import numpy as np
from datetime import datetime, timedelta
from fastapi import HTTPException

from database.enums import BloomTaxonomy
from services.crud_services import read_query, read_one
from services.inference_service import performance_forecaster, passing_predictor, AIInferenceEngine as ai_engine

# --- HELPER: Competency Name Resolution ---
async def get_competency_map() -> Dict[str, str]:
    """
    Helper to build a map of {competency_id: competency_name}.
    """
    comp_map = {}
    
    # 1. Try Flat Collection
    all_competencies = await read_query("competencies", [])
    for c in all_competencies:
        name = c["data"].get("description") or c["data"].get("title") or c["data"].get("code") or "Unknown"
        comp_map[c["id"]] = name

    # 2. If map is incomplete, check Subjects -> Topics (Embedded)
    subjects = await read_query("subjects", [])
    for sub in subjects:
        topics = sub["data"].get("topics", [])
        for topic in topics:
            comps = topic.get("competencies", []) if isinstance(topic, dict) else getattr(topic, "competencies", [])
            for comp in comps:
                c_id = comp.get("id") or comp.get("code")
                c_name = comp.get("description") or comp.get("code") or "Unknown Competency"
                if c_id:
                    comp_map[c_id] = c_name

    return comp_map

async def calculate_passing_rate(subject_id: Optional[str] = None, assessment_id: Optional[str] = None) -> Dict:
    filters = []
    if subject_id:
        filters.append(("subject_id", "==", subject_id))
    if assessment_id:
        filters.append(("assessment_id", "==", assessment_id))
    
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
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_info = profile.get("student_info", {})
    
    submissions = await read_query("assessment_submissions", [
        ("user_id", "==", user_id),
        ("subject_id", "==", subject_id)
    ])
    
    avg_score = 0.0
    if submissions:
        scores = [s["data"].get("score", 0) for s in submissions]
        avg_score = statistics.mean(scores) if scores else 0.0
    
    probability = min(1.0, avg_score / 100.0)
    if len(submissions) > 3:
        probability = min(1.0, probability + 0.05)

    if probability >= 0.85:
        risk_level = "Low Risk"
        status = "On Track"
        recommendation = "Maintain current study habits; ready for advanced topics."
    elif probability >= 0.65:
        risk_level = "Moderate Risk"
        status = "Proficient"
        recommendation = "Review specific weak areas; consistent practice needed."
    elif probability >= 0.50:
        risk_level = "High Risk"
        status = "At Risk"
        recommendation = "Immediate intervention required; schedule consultation."
    else:
        risk_level = "Critical"
        status = "Critical"
        recommendation = "Urgent: Student is significantly behind."

    return {
        "user_id": user_id,
        "subject_id": subject_id,
        "passing_probability": probability,
        "risk_level": risk_level,
        "status": status,
        "recommendation": recommendation,
        "contributing_factors": {
            "average_score": avg_score,
            "assessments_taken": len(submissions)
        }
    }

async def analyze_student_weaknesses(user_id: str, subject_id: str) -> Dict:
    submissions = await read_query("assessment_submissions", [
        ("user_id", "==", user_id),
        ("subject_id", "==", subject_id)
    ])
    
    if not submissions:
        return {"weaknesses": [], "recommendations": [], "message": "No assessment data available"}

    competency_map = await get_competency_map()
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
    
    weaknesses = []
    for comp_id, stats in competency_scores.items():
        mastery = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        name = competency_map.get(comp_id, f"Competency {comp_id}")
        
        if mastery >= 85: status = "Mastery"; rec="Ready for advanced modules."; risk = "Low"
        elif mastery >= 70: status = "Proficient"; rec="Continue current study path."; risk = "Low"
        elif mastery >= 50: status = "Developing"; rec="Review core concepts."; risk = "Medium"
        else: status = "Critical"; rec="Immediate revision required."; risk = "High"

        weaknesses.append({
            "competency_id": comp_id,
            "competency_name": name,
            "mastery_percentage": round(mastery, 1),
            "predicted_score": round(mastery, 1),
            "correct_answers": stats["correct"],
            "total_attempts": stats["total"],
            "status": status,
            "risk_level": risk,
            "recommendation": rec
        })
    
    weaknesses.sort(key=lambda x: x["mastery_percentage"])
    recommendations = await recommend_study_modules(user_id, subject_id, weaknesses)
    
    return {
        "user_id": user_id,
        "subject_id": subject_id,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "total_competencies_assessed": len(competency_scores)
    }

async def recommend_study_modules(user_id: str, subject_id: str, weaknesses: List[Dict]) -> List[Dict]:
    if not weaknesses: return []
    
    profile = await read_one("user_profiles", user_id)
    behavior_profile = profile.get("student_info", {}).get("behavior_profile", {})
    subject = await read_one("subjects", subject_id)
    if not subject: return []
    
    recommendations = []
    weak_competency_ids = [w["competency_id"] for w in weaknesses if w["mastery_percentage"] < 70]
    
    for topic in subject.get("topics", []):
        for competency in topic.get("competencies", []):
            c_id = competency.get("id") or competency.get("code")
            if c_id in weak_competency_ids:
                if topic.get("lecture_content"):
                    weakness_severity = next((w["mastery_percentage"] for w in weaknesses if w["competency_id"] == c_id), 50)
                    priority = 100 - weakness_severity
                    
                    recommendations.append({
                        "topic_id": topic.get("id", "unknown"),
                        "topic_title": topic.get("title", "Topic"),
                        "competency_code": competency.get("code"),
                        "competency_description": competency.get("description"),
                        "priority": priority,
                        "estimated_study_time": calculate_estimated_time(behavior_profile, topic),
                        "module_url": topic.get("lecture_content")
                    })
                    break
    
    recommendations.sort(key=lambda x: x["priority"], reverse=True)
    return recommendations[:10]

def calculate_estimated_time(behavior_profile: Dict, topic: Dict) -> str:
    base_time = 60
    pace = behavior_profile.get("learning_pace", "Standard")
    if pace == "Fast": estimated = base_time * 0.7
    elif pace == "Slow": estimated = base_time * 1.3
    else: estimated = base_time
    
    hours = int(estimated // 60)
    minutes = int(estimated % 60)
    return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

async def get_subject_analytics(subject_id: str) -> Dict:
    students = await read_query("user_profiles", [])
    student_ids = [s["id"] for s in students if s["data"].get("role_id") == "student"]
    passing_data = await calculate_passing_rate(subject_id=subject_id)
    topic_difficulties = await analyze_topic_difficulty(subject_id)
    
    total_completion = 0
    completion_count = 0
    for student_id in student_ids:
        profile = await read_one("user_profiles", student_id)
        if profile:
            reports = profile.get("student_info", {}).get("progress_report", [])
            for report in reports:
                if report.get("subject_id") == subject_id:
                    total_completion += report.get("overall_completeness", 0)
                    completion_count += 1
    
    avg_completion = (total_completion / completion_count) if completion_count > 0 else 0
    
    return {
        "subject_id": subject_id,
        "passing_statistics": passing_data,
        "average_completion_rate": avg_completion,
        "total_students": len(student_ids),
        "difficult_topics": topic_difficulties[:5],
        "engagement_metrics": await get_engagement_metrics(subject_id)
    }

async def analyze_topic_difficulty(subject_id: str) -> List[Dict]:
    submissions = await read_query("assessment_submissions", [("subject_id", "==", subject_id)])
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
                if is_correct: topic_performance[topic_id]["correct"] += 1
    
    difficulties = []
    for topic_id, stats in topic_performance.items():
        success_rate = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        difficulties.append({
            "topic_id": topic_id,
            "difficulty_score": 100 - success_rate,
            "success_rate": success_rate,
            "attempts": stats["total"]
        })
    difficulties.sort(key=lambda x: x["difficulty_score"], reverse=True)
    return difficulties

async def get_engagement_metrics(subject_id: str) -> Dict:
    study_logs = await read_query("study_logs", [("resource_type", "==", "module")])
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
    Fixed: Now includes Subject Breakdown and Bloom's Performance.
    """
    all_users = await read_query("user_profiles", [])
    submissions = await read_query("assessment_submissions", [])
    all_assessments = await read_query("assessments", []) 
    all_subjects = await read_query("subjects", []) # [FIX] Fetch subjects

    # Map Subject ID -> Title
    subject_map = {s["id"]: s["data"].get("title", "Unknown Subject") for s in all_subjects}

    # Map Assessment -> Questions -> Bloom Level
    assessment_bloom_map = {}
    for a in all_assessments:
        q_data = {}
        for q in a["data"].get("questions", []):
            raw_bloom = q.get("bloom_taxonomy", "remembering")
            if hasattr(raw_bloom, "value"): bloom_val = str(raw_bloom.value).lower()
            else: bloom_val = str(raw_bloom).lower()
            
            qid = q.get("id") or q.get("question_id")
            if qid: q_data[qid] = bloom_val
        assessment_bloom_map[a["id"]] = q_data
    
    student_scores = {}
    subject_stats = {} # [FIX] Initialize subject stats container
    pass_count = 0
    fail_count = 0
    bloom_stats = {b.value.lower(): {"total": 0, "correct": 0} for b in BloomTaxonomy}
    
    for sub in submissions:
        data = sub["data"]
        uid = data.get("user_id")
        score = data.get("score", 0)
        aid = data.get("assessment_id")
        sid = data.get("subject_id") # Get Subject ID
        
        # User Score Aggregation
        if uid not in student_scores: student_scores[uid] = []
        student_scores[uid].append(score)

        # Subject Aggregation [FIX]
        if sid:
            if sid not in subject_stats: subject_stats[sid] = {"total": 0, "count": 0}
            subject_stats[sid]["total"] += score
            subject_stats[sid]["count"] += 1

        # Bloom Aggregation
        q_lookup = assessment_bloom_map.get(aid, {})
        answers = data.get("answers", [])
        for ans in answers:
            qid = ans.get("question_id")
            is_correct = ans.get("is_correct", False)
            bloom = q_lookup.get(qid)
            if bloom and bloom in bloom_stats:
                bloom_stats[bloom]["total"] += 1
                if is_correct: bloom_stats[bloom]["correct"] += 1
        
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

    # [FIX] Populate Global Subjects List
    global_subjects = []
    for sid, stats in subject_stats.items():
        if stats["count"] > 0:
            avg_score = stats["total"] / stats["count"]
            global_subjects.append({
                "subject_id": sid,
                "title": subject_map.get(sid, "General"),
                "passing_rate": round(avg_score, 1) # Note: Frontend interface uses passing_rate as score for now
            })
    global_subjects.sort(key=lambda x: x["passing_rate"])

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
        "subjects": global_subjects, # [FIX] No longer empty!
        "performance_by_bloom": global_bloom
    }

async def get_student_comprehensive_report(user_id: str) -> Dict:
    """
    Generate a full analytics report including Subject-Specific Performance, Competency Analysis, and Bloom Stats.
    """
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")

    student_info = profile.get("student_info", {})
    behavior_profile = student_info.get("behavior_profile", {})
    progress_reports = student_info.get("progress_report", [])
    
    submissions = await read_query("assessment_submissions", [("user_id", "==", user_id)])
    all_subjects = await read_query("subjects", [])
    subject_map = {s["id"]: s["data"].get("title", "Unknown Subject") for s in all_subjects}
    competency_map = await get_competency_map()

    # Prepare Bloom Mapping
    all_assessments = await read_query("assessments", [])
    assessment_bloom_map = {}
    for a in all_assessments:
        q_data = {}
        for q in a["data"].get("questions", []):
            raw_bloom = q.get("bloom_taxonomy", "remembering")
            bloom_val = str(raw_bloom.value).lower() if hasattr(raw_bloom, "value") else str(raw_bloom).lower()
            qid = q.get("id") or q.get("question_id")
            if qid: q_data[qid] = bloom_val
        assessment_bloom_map[a["id"]] = q_data

    bloom_stats = {b.value.lower(): {"total": 0, "correct": 0} for b in BloomTaxonomy}
    scores = []
    subject_stats = {}
    competency_scores = {}

    for sub in submissions:
        data = sub["data"]
        score = data.get("score", 0)
        scores.append(score)
        
        sid = data.get("subject_id")
        if sid not in subject_stats: subject_stats[sid] = {"total_score": 0, "count": 0}
        subject_stats[sid]["total_score"] += score
        subject_stats[sid]["count"] += 1

        answers = data.get("answers", [])
        aid = data.get("assessment_id")
        q_lookup = assessment_bloom_map.get(aid, {})

        for ans in answers:
            is_correct = ans.get("is_correct", False)
            
            # Competency
            cid = ans.get("competency_id")
            if cid:
                if cid not in competency_scores: competency_scores[cid] = {"correct": 0, "total": 0}
                competency_scores[cid]["total"] += 1
                if is_correct: competency_scores[cid]["correct"] += 1
            
            # Bloom
            qid = ans.get("question_id")
            bloom = q_lookup.get(qid)
            if bloom and bloom in bloom_stats:
                bloom_stats[bloom]["total"] += 1
                if is_correct: bloom_stats[bloom]["correct"] += 1

    student_bloom_performance = {}
    for level, stats in bloom_stats.items():
        if stats["total"] > 0:
            student_bloom_performance[level] = round((stats["correct"] / stats["total"]) * 100, 1)
        else:
            student_bloom_performance[level] = 0

    avg_score = statistics.mean(scores) if scores else 0.0
    merged_subject_performance = []
    unique_sids = set(subject_stats.keys()) | {pr.get("subject_id") for pr in progress_reports}
    
    for sid in unique_sids:
        stats = subject_stats.get(sid, {"total_score": 0, "count": 0})
        avg_perf = stats["total_score"] / stats["count"] if stats["count"] > 0 else 0
        prog = next((p for p in progress_reports if p.get("subject_id") == sid), {})
        
        merged_subject_performance.append({
            "subject_id": sid,
            "subject_title": subject_map.get(sid, "General Education"),
            "average_score": round(avg_perf, 2),
            "assessments_taken": stats["count"],
            "modules_completeness": prog.get("modules_completeness", 0),
            "assessment_completeness": prog.get("assessment_completeness", 0),
            "overall_completeness": prog.get("overall_completeness", 0),
            "status": "Needs Review" if avg_perf < 75 else "Good Standing"
        })
    merged_subject_performance.sort(key=lambda x: x["average_score"])

    probability = min(1.0, avg_score / 100.0)
    if len(submissions) > 5: probability = min(1.0, probability + 0.05)
    
    if probability >= 0.75: risk_level = "Low Risk"; recommendation = "Maintain current study habits."
    elif probability >= 0.60: risk_level = "Moderate Risk"; recommendation = "Focus on the subjects highlighted in 'Needs Review'."
    else: risk_level = "High Risk"; recommendation = "Urgent: Complete diagnostic tests for core subjects."

    weaknesses = []
    for cid, stats in competency_scores.items():
        mastery = (stats["correct"] / stats["total"]) * 100
        name = competency_map.get(cid, f"Competency {cid}")
        
        if mastery >= 85: status = "Mastery"; risk = "Low"
        elif mastery >= 75: status = "Proficient"; risk = "Low"
        elif mastery >= 50: status = "Developing"; risk = "Medium"
        else: status = "Critical"; risk = "High"

        weaknesses.append({
            "competency_id": cid,
            "competency_name": name,
            "mastery": round(mastery, 1),
            "status": status,
            "risk_level": risk,
            "attempts": stats["total"]
        })
    weaknesses.sort(key=lambda x: x["mastery"])

    return {
        "student_profile": {
            "name": f"{profile.get('first_name', '')} {profile.get('last_name', '')}",
            "email": profile.get("email"),
            "id": user_id
        },
        "behavioral_traits": {
            "average_session_length": behavior_profile.get("average_session_length", 0),
            "preferred_study_time": behavior_profile.get("preferred_study_time", "Any"),
            "interruption_frequency": behavior_profile.get("interruption_frequency", "Low"),
            "learning_pace": behavior_profile.get("learning_pace", "Standard"),
            "timeliness_score": student_info.get("timeliness", 0),
            "personal_readiness": student_info.get("personal_readiness", "Unknown"),
            "confident_subjects": student_info.get("confident_subject", [])
        },
        "overall_performance": {
            "average_score": round(avg_score, 2),
            "total_assessments": len(submissions),
            "passing_probability": round(probability * 100, 2),
            "risk_level": risk_level,
            "recommendation": recommendation
        },
        "subject_performance": merged_subject_performance,
        "weaknesses": weaknesses[:5],
        "performance_by_bloom": student_bloom_performance,
        "recent_activity": submissions[-5:] 
    }

def get_avg_completion(student_info: Dict) -> float:
    reports = student_info.get("progress_report", [])
    if not reports: return 0.0
    return sum(r.get("overall_completeness", 0) for r in reports) / len(reports)