from fastapi import FastAPI, UploadFile, File, Form, Depends
from pydantic import BaseModel
from supabase import create_client
import google.generativeai as genai
import os
import uuid
from dotenv import load_dotenv
import tempfile
# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI()

# Pydantic Models
class UserSignup(BaseModel):
    name: str
    email: str

class AIRequest(BaseModel):
    note_id: str

# User Registration
@app.post("/signup")
def signup(user: UserSignup):
    try:
        data, _ = supabase.table("users").insert({
            "name": user.name,
            "email": user.email
        }).execute()
        return {"success": True, "message": "User registered successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Upload Notes (Text, Audio, Video)
@app.post("/upload-note")
async def upload_note(
    user_id: str = Form(...),
    text_content: str = Form(None),
    file: UploadFile = File(None)
):
    file_url = None
    file_type = None  

    if file:
        file_ext = file.filename.split(".")[-1].lower()
        file_name = f"{uuid.uuid4()}.{file_ext}"

        # Determine file type
        file_type = (
            "audio" if file_ext in ["mp3", "wav", "aac"] else
            "video" if file_ext in ["mp4", "avi", "mov"] else
            "pdf" if file_ext in ["pdf"] else
            "image" if file_ext in ["jpg", "png", "jpeg"] else
            "text"
        )

        # Save file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name

        try:
            # Upload file from local temp path to Supabase Storage
            supabase.storage.from_("notes-storage").upload(file_name, temp_file_path)
            file_url = f"{SUPABASE_URL}/storage/v1/object/public/notes-storage/{file_name}"
        except Exception as e:
            return {"success": False, "message": "File upload failed", "error": str(e)}
        finally:
            os.remove(temp_file_path)  # Cleanup temp file

    try:
        # Insert into Supabase table
        supabase.table("notes").insert({
            "user_id": user_id,
            "file_url": file_url,
            "file_type": file_type,
            "text_content": text_content
        }).execute()
    except Exception as e:
        return {"success": False, "message": "Database insert failed", "error": str(e)}

    return {
        "success": True,
        "message": "Note saved successfully",
        "file_url": file_url,
        "file_type": file_type,
        "text_content": text_content
    }

# AI Insights (Summarization, Sentiment Analysis)
import requests

@app.post("/generate-insights")
def generate_insights(ai_request: AIRequest):
    try:
        # Fetch note details from Supabase
        note_data = supabase.table("notes").select("file_url").eq("id", ai_request.note_id).execute()
        if not note_data.data:
            return {"success": False, "message": "Note not found"}

        file_url = note_data.data[0]["file_url"]

        # Download file content
        response = requests.get(file_url)
        if response.status_code != 200:
            return {"success": False, "message": "Failed to download file"}

        file_content = response.content.decode("utf-8", errors="ignore")

        # Process with Gemini AI
        #model = genai.GenerativeModel("gemini-1.5-pro")  # ✅ Correct model name
        model = genai.GenerativeModel("gemini-1.5-flash")

        ai_response = model.generate_content(file_content)

        # Store AI insights
        supabase.table("ai_insights").insert({
            "note_id": ai_request.note_id,
            "summary": ai_response.text
        }).execute()

        return {"success": True, "message": "AI insights generated", "summary": ai_response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

