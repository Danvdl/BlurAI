from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from celery import Celery
import shutil
import os
from pathlib import Path
from image_processor import blur_background, blur_faces, apply_gaussian_blur, blur_with_mask

app = FastAPI(title="BlurAI Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create directories for uploads and outputs
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Celery configuration
celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@app.get("/")
def read_root():
    return {"message": "Welcome to BlurAI API", "version": "1.0.0"}

@app.post("/segment")
async def segment_image(file: UploadFile = File(...)):
    # Placeholder for SAM2 segmentation
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "segments": [], "message": "Segmentation queued"}

@app.post("/blur-image")
async def blur_image(
    file: UploadFile = File(...), 
    blur_type: str = Form("background"),
    mask: UploadFile = File(None),
    blur_strength: int = Form(30),
    blur_shape: str = Form("rect"),
    blur_style: str = Form("smooth")
):
    # Save uploaded file
    file_path = UPLOAD_DIR / file.filename
    output_filename = f"blurred_{file.filename}"
    output_path = OUTPUT_DIR / output_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Save mask if provided
    mask_path = None
    if mask:
        mask_path = UPLOAD_DIR / f"mask_{file.filename}.png"
        with open(mask_path, "wb") as buffer:
            shutil.copyfileobj(mask.file, buffer)

    # Apply the appropriate blur based on blur_type
    try:
        if mask_path:
            result_path = blur_with_mask(file_path, mask_path, output_path)
        elif blur_type == "background":
            result_path = blur_background(file_path, output_path)
        elif blur_type == "faces":
            result_path = blur_faces(file_path, output_path, strength=blur_strength, shape=blur_shape, style=blur_style)
        else:
            # Default to simple Gaussian blur
            result_path = apply_gaussian_blur(file_path, output_path)
        
        # Return the blurred image file
        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename=output_filename
        )
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to process image"
        }

@app.post("/blur-video")
async def blur_video(file: UploadFile = File(...), blur_type: str = Form("background")):
    """Upload a video for blurring processing"""
    # Save uploaded video
    video_path = UPLOAD_DIR / file.filename
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Generate a job ID
    import uuid
    job_id = str(uuid.uuid4())
    
    # Queue the video processing task (placeholder for now)
    # In production, this would use Celery to process in background
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Video processing queued. Job ID: {job_id}"
    }

@app.get("/video-status/{job_id}")
async def get_video_status(job_id: str):
    """Check the status of a video processing job"""
    # Placeholder - in production this would check Celery task status
    return {
        "job_id": job_id,
        "status": "processing",
        "progress": 45,
        "message": "Processing video frames..."
    }
