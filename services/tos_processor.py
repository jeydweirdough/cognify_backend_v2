import json
import google.generativeai as genai
from groq import Groq
from core.config import settings
from database.models import SubjectSchema

# 1. Initialize Clients
genai.configure(api_key=settings.GOOGLE_API_KEY)
groq_client = Groq(api_key=settings.GROQ_API_KEY)

async def process_tos_document(file_content: bytes, filename: str) -> SubjectSchema:
    """
    Main function called by the API Route.
    """
    # Phase 1: Vision Extraction (Gemini)
    raw_json_data = await _extract_structure_with_gemini(file_content)
    
    # Phase 2: Logic & Schema Mapping (Llama 3)
    structured_data = await _map_to_schema_with_llama(raw_json_data)
    
    return structured_data

async def _extract_structure_with_gemini(content: bytes):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    You are a data extractor. Analyze this Table of Specifications (TOS) image/PDF.
    Extract the hierarchy into this JSON format:
    {
        "subject_title": "string",
        "pqf_level": "integer (6 or 7)",
        "topics": [
            {
                "topic_title": "string",
                "weight_percent": "float",
                "competencies": [
                    {
                        "code": "string (e.g. 1.1)",
                        "description": "string",
                        "bloom_level": "string (e.g. Remembering)",
                        "item_count": "integer"
                    }
                ]
            }
        ]
    }
    Return ONLY JSON.
    """
    
    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": content}
    ])
    
    # Clean the response string
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_text)

async def _map_to_schema_with_llama(raw_data: dict) -> SubjectSchema:
    # We provide the exact Pydantic schema structure to Llama
    prompt = f"""
    You are a database admin. Convert this raw data into a specific database schema.
    
    RAW DATA:
    {json.dumps(raw_data)}
    
    CONVERSION RULES:
    1. Bloom's "Remembering/Understanding" -> Difficulty "Easy"
    2. Bloom's "Applying/Analyzing" -> Difficulty "Moderate"
    3. Bloom's "Evaluating/Creating" -> Difficulty "Difficult"
    4. Ensure "pqf_level" is an integer.
    
    OUTPUT SCHEMA (JSON):
    {{
      "id": "auto_generated_id",
      "title": "Subject Title",
      "pqf_level": 6,
      "total_weight_percentage": 100.0,
      "topics": [
        {{
          "id": "auto_generated_topic_id",
          "title": "Topic Name",
          "weight_percentage": 20.0,
          "competencies": [
             {{
                "id": "auto_generated_comp_id",
                "code": "1.1",
                "description": "text",
                "target_bloom_level": "remembering", 
                "target_difficulty": "Easy",
                "allocated_items": 5
             }}
          ]
        }}
      ]
    }}
    """

    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"}
    )
    
    result = json.loads(completion.choices[0].message.content)
    
    # Validate with your actual Pydantic model to ensure it fits the DB
    return SubjectSchema(**result)