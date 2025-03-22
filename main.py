from fastapi import FastAPI, UploadFile, File, Form
from io import BytesIO
from supabase import create_client
import os
import uuid

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

@app.post("/upload-audio")
async def upload_audio(user_id: str = Form(...), file: UploadFile = File(...)):
    file_ext = file.filename.split(".")[-1]
    file_name = f"{uuid.uuid4()}.{file_ext}"  # Generate unique filename

    # Read the file content as bytes
    file_bytes = await file.read()

    # Upload using raw bytes
    try:
        response = supabase.storage.from_("audio-notes").upload(
            file_name, file_bytes, {"content-type": file.content_type}  # ✅ Fix applied here
        )
    except Exception as e:
        return {"success": False, "message": "Upload failed", "error": str(e)}

    # Construct public URL
    audio_url = f"{SUPABASE_URL}/storage/v1/object/public/audio-notes/{file_name}"

    # Insert into Supabase database
    try:
        data, _ = supabase.table("notes").insert({
            "user_id": user_id,
            "audio_url": audio_url
        }).execute()
    except Exception as e:
        return {"success": False, "message": "Database insert failed", "error": str(e)}

    return {"success": True, "audio_url": audio_url}
