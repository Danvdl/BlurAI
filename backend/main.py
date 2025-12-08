from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from celery import Celery
import shutil
import os
from pathlib import Path
from image_processor import blur_background, blur_faces, apply_gaussian_blur, blur_with_mask
import video_processor
import uuid
from utils.logger import logger

app = FastAPI(title="BlurAI Backend")

# Middleware for logging requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Request completed: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}", exc_info=True)
        raise

# In-memory job store (replace with Redis/Database in production)
video_jobs = {}

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
    logger.info(f"Processing image blur: {file.filename}, type={blur_type}, shape={blur_shape}")
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
        
        logger.info(f"Image processed successfully: {output_path}")
        # Return the blurred image file
        return FileResponse(
            result_path,
            media_type="image/jpeg",
            filename=output_filename
        )
    except Exception as e:
        logger.error(f"Error processing image {file.filename}: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "message": "Failed to process image"
        }

def process_video_task(job_id: str, video_path: Path, output_path: Path, blur_type: str, blur_strength: int, blur_shape: str, blur_style: str):
    """Background task for video processing"""
    logger.info(f"Starting video job {job_id} for {video_path.name}")
    try:
        video_jobs[job_id]["status"] = "processing"
        video_jobs[job_id]["progress"] = 0.0
        
        def update_progress(progress):
            video_jobs[job_id]["progress"] = progress
            if int(progress * 100) % 10 == 0: # Log every 10%
                logger.debug(f"Job {job_id} progress: {progress*100:.1f}%")
            
        video_processor.process_video(
            video_path, 
            output_path, 
            blur_type=blur_type,
            blur_strength=blur_strength,
            blur_shape=blur_shape,
            blur_style=blur_style,
            progress_callback=update_progress
        )
        
        video_jobs[job_id]["status"] = "completed"
        video_jobs[job_id]["progress"] = 1.0
        video_jobs[job_id]["result_url"] = f"/download-video/{output_path.name}"
        logger.info(f"Video job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Video processing failed for job {job_id}: {e}", exc_info=True)
        video_jobs[job_id]["status"] = "failed"
        video_jobs[job_id]["error"] = str(e)

@app.post("/blur-video")
async def blur_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    blur_type: str = Form("faces"),
    blur_strength: int = Form(30),
    blur_shape: str = Form("rect"),
    blur_style: str = Form("smooth")
):
    """Upload a video for blurring processing"""
    logger.info(f"Received video upload: {file.filename}")
    # Save uploaded video
    video_path = UPLOAD_DIR / file.filename
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Generate a job ID
    job_id = str(uuid.uuid4())
    output_filename = f"processed_{file.filename}"
    output_path = OUTPUT_DIR / output_filename
    
    # Initialize job status
    video_jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 0.0,
        "filename": file.filename
    }
    
    logger.info(f"Queued video job {job_id}")
    
    # Queue the video processing task
    background_tasks.add_task(
        process_video_task, 
        job_id, 
        video_path, 
        output_path, 
        blur_type,
        blur_strength,
        blur_shape,
        blur_style
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Video processing queued. Job ID: {job_id}"
    }

@app.get("/video-status/{job_id}")
async def get_video_status(job_id: str):
    """Check the status of a video processing job"""
    if job_id not in video_jobs:
        return {"error": "Job not found"}
    
    return video_jobs[job_id]

@app.get("/download-video/{filename}")
async def download_video(filename: str):
    """Download a processed video"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}
        
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=filename
    )
