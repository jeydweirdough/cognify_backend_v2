import json
import google.generativeai as genai
from groq import Groq
from core.config import settings
from services.crud_services import read_one
from fastapi import HTTPException

# Initialize AI Clients
genai.configure(api_key=settings.GOOGLE_API_KEY)
groq_client = Groq(api_key=settings.GROQ_API_KEY)

async def auto_categorize_module(file_content: bytes, subject_id: str):
    """
    1. Fetches the TOS Blueprint (Subject) from Firestore.
    2. Reads the Uploaded Module using Gemini.
    3. Matches Module Content to TOS Topics using Llama 3.
    """
    
    # A. Fetch the TOS Blueprint from Database
    # We need the "Map" to compare against
    subject_data = await read_one("subjects", subject_id)
    if not subject_data:
        raise HTTPException(status_code=404, detail="Subject TOS not found. Please upload TOS first.")

    # B. Extract Content from the Uploaded Module (Gemini Vision)
    module_text_summary = await _extract_module_content(file_content)
    
    # C. Compare and Match (Llama 3 Logic)
    # We send the TOS Structure + Module Summary to Llama
    match_result = await _find_best_fit_topic(subject_data, module_text_summary)
    
    return match_result

async def _extract_module_content(content: bytes):
    """
    Uses Gemini to read the file and summarize its key concepts.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """
    Read this educational module/handout. 
    Summarize the key topics, theories, and concepts covered. 
    Focus on specific terminologies (e.g., 'Id, Ego, Superego' or 'ANOVA').
    Keep it concise (under 300 words).
    """
    
    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": content}
    ])
    return response.text

async def _find_best_fit_topic(tos_data: dict, module_summary: str):
    """
    Uses Llama 3 to act as the 'Librarian'.
    It looks at the TOS topics and the Module summary and picks the winner.
    """
    
    # Prepare a simplified list of topics for Llama to read
    # We don't need the full heavy JSON, just IDs and Titles
    tos_structure = [
        {"id": t["id"], "title": t["title"], "competencies": [c["description"] for c in t["competencies"]]} 
        for t in tos_data.get("topics", [])
    ]
    
    prompt = f"""
    You are a Curriculum Alignment AI.
    
    TASK:
    Match this Uploaded Module to the correct Topic in the Table of Specifications (TOS).
    
    CONTEXT (The TOS Blueprint):
    {json.dumps(tos_structure)}
    
    UPLOADED MODULE CONTENT:
    {module_summary}
    
    INSTRUCTIONS:
    1. Compare the module content to the TOS Topics and Competencies.
    2. Identify the single best matching Topic ID.
    3. Return a JSON object with:
       - matched_topic_id
       - confidence_score (0-100)
       - reasoning (Why did you pick this?)
    """

    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"}
    )
    
    return json.loads(completion.choices[0].message.content)