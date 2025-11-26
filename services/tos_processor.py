import json
import typing_extensions
import google.generativeai as genai
from core.config import settings
from database.models import SubjectSchema
from fastapi import HTTPException

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

async def process_tos_document(file_content: bytes, filename: str) -> SubjectSchema:
    """
    Sends the TOS PDF to Gemini to extract the Subject, Topics, and Competencies structure.
    Returns a validated SubjectSchema object.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # We define the JSON structure we want Gemini to return strictly
    # This helps ensure the AI output matches our Pydantic models
    prompt = """
    You are an expert Curriculum Developer. 
    Analyze the attached Table of Specifications (TOS) PDF.
    
    Extract the data into a JSON object that strictly matches this structure:
    {
        "id": "generate_unique_string_id",
        "title": "Subject Title (e.g., Advanced Personality Theory)",
        "pqf_level": 6,
        "total_weight_percentage": 100.0,
        "topics": [
            {
                "id": "generate_unique_string_id",
                "title": "Topic Name",
                "weight_percentage": 15.0,
                "competencies": [
                    {
                        "id": "generate_unique_string_id",
                        "code": "1.1",
                        "description": "Competency description...",
                        "target_bloom_level": "remembering",
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
    1. 'target_bloom_level' must be one of: remembering, understanding, applying, analyzing, evaluating, creating.
    2. 'target_difficulty' must be one of: Easy, Moderate, Difficult.
    3. Ensure percentages sum up correctly if possible, but prioritize extracting what is in the document.
    4. Return ONLY the raw JSON string. Do not include markdown formatting (```json).
    """

    try:
        response = model.generate_content([
            prompt,
            {"mime_type": "application/pdf", "data": file_content}
        ])
        
        # Clean up response text if it contains markdown code blocks
        clean_json = response.text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
            
        data = json.loads(clean_json)
        
        # Validate using Pydantic
        subject = SubjectSchema(**data)
        return subject

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI failed to generate valid JSON structure for this TOS.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TOS Processing Error: {str(e)}")