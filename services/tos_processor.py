import json
import typing_extensions
import google.generativeai as genai
from core.config import settings
from database.models import SubjectSchema
from fastapi import HTTPException
import logging

# Configure Logging
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

async def get_working_model():
    """
    Iterates through preferred models to find one that is available.
    Returns a configured GenerativeModel.
    """
    candidate_models = [
        'gemini-2.0-flash',       
        'gemini-1.5-flash',       
        'gemini-1.5-flash-001',   
        'gemini-1.5-pro',         
        'gemini-pro'              
    ]

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            return model_name, model
        except Exception:
            continue
            
    return 'gemini-1.5-flash', genai.GenerativeModel('gemini-1.5-flash')

async def process_tos_document(file_content: bytes, filename: str) -> SubjectSchema:
    """
    Sends the TOS PDF to Gemini to extract the Subject, Topics, and Competencies structure.
    Returns a validated SubjectSchema object.
    """
    
    # [FIX] Updated Prompt to match SubjectSchema exactly (Removed root 'id', added 'description')
    prompt = """
    You are an expert Curriculum Developer. 
    Analyze the attached Table of Specifications (TOS) PDF.
    
    Extract the data into a JSON object that strictly matches this structure.
    DO NOT include an 'id' field for the root Subject object.
    
    Structure:
    {
        "title": "Subject Title (e.g., Advanced Personality Theory)",
        "description": "A brief summary of the subject based on the document.",
        "pqf_level": 6,
        "total_weight_percentage": 100.0,
        "topics": [
            {
                "id": "generate_unique_string_id_here",
                "title": "Topic Name",
                "weight_percentage": 15.0,
                "competencies": [
                    {
                        "id": "generate_unique_string_id_here",
                        "code": "1.1",
                        "description": "Competency description...",
                        "target_bloom_level": "Remembering",
                        "target_difficulty": "Easy",
                        "allocated_items": 5
                    }
                ],
                "lecture_content": null,
                "image": null
            }
        ]
    }
    
    RULES:
    1. 'target_bloom_level' must be one of: Remembering, Understanding, Applying, Analyzing, Evaluating, Creating.
    2. 'target_difficulty' must be one of: Easy, Moderate, Difficult.
    3. Ensure percentages sum up correctly if possible.
    4. Return ONLY the raw JSON string. Do not include markdown formatting (```json).
    """

    candidate_models = [
        'gemini-2.0-flash', 
        'gemini-1.5-flash', 
        'gemini-1.5-flash-001',
        'gemini-1.5-pro',
        'gemini-pro'
    ]

    last_error = None

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([
                prompt,
                {"mime_type": "application/pdf", "data": file_content}
            ])
            
            clean_json = response.text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
                
            data = json.loads(clean_json)
            
            # [FIX] Validation: Ensure strict Pydantic parsing
            subject = SubjectSchema(**data)
            return subject

        except Exception as e:
            error_str = str(e)
            last_error = error_str
            if "404" in error_str or "not found" in error_str.lower():
                print(f"Model {model_name} failed (Not Found). Retrying...")
                continue
            else:
                break

    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except:
        available_models = ["Could not list models"]

    raise HTTPException(
        status_code=500, 
        detail=f"AI Processing Failed. Models returned 404 or failed. Last Error: {last_error}. Available: {available_models}"
    )