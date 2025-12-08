"""
Video processing module for BlurAI.
Handles video frame extraction, processing, and reassembly.
"""

import cv2
import ffmpeg
import static_ffmpeg
import numpy as np
from pathlib import Path
from typing import List, Tuple, Callable
import shutil
import image_processor
from utils.logger import logger

# Initialize static ffmpeg paths
static_ffmpeg.add_paths()

def extract_frames(video_path: Path, output_dir: Path) -> Tuple[List[Path], float]:
    """
    Extract frames from a video file.
    
    Args:
        video_path: Path to the input video
        output_dir: Directory to save extracted frames
    
    Returns:
        Tuple of (list of frame paths, fps)
    """
    logger.info(f"Extracting frames from {video_path} to {output_dir}")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Open the video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Failed to open video file: {video_path}")
        raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames_est = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.debug(f"Video FPS: {fps}, Estimated frames: {total_frames_est}")
    
    frame_paths = []
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_path = output_dir / f"{frame_count:05d}.jpg"
        cv2.imwrite(str(frame_path), frame)
        frame_paths.append(frame_path)
        frame_count += 1
        
        if frame_count % 100 == 0:
            logger.debug(f"Extracted {frame_count} frames...")
    
    cap.release()
    logger.info(f"Extraction complete. Total frames: {frame_count}")
    return frame_paths, fps


def reassemble_video(frame_dir: Path, output_path: Path, fps: float, audio_path: Path = None):
    """
    Reassemble frames into a video with optional audio.
    
    Args:
        frame_dir: Directory containing processed frames
        output_path: Path for the output video
        fps: Frames per second
        audio_path: Optional path to original video for audio extraction
    """
    logger.info(f"Reassembling video from {frame_dir} to {output_path}")
    # Get all frame files
    frames = sorted(frame_dir.glob("*.jpg"))
    
    if not frames:
        logger.error("No frames found for reassembly")
        raise ValueError("No frames found in directory")
    
    # Read first frame to get dimensions
    first_frame = cv2.imread(str(frames[0]))
    height, width = first_frame.shape[:2]
    
    # Create video writer
    # Use mp4v codec
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    # Write all frames
    for i, frame_path in enumerate(frames):
        frame = cv2.imread(str(frame_path))
        out.write(frame)
        if i % 100 == 0:
            logger.debug(f"Wrote {i} frames to video...")
    
    out.release()
    logger.info("Video reassembly (visuals) complete")
    
    # If audio path is provided, merge audio with video
    if audio_path and audio_path.exists():
        logger.info("Merging audio...")
        temp_output = output_path.with_suffix('.temp.mp4')
        # Rename the silent video to temp
        if output_path.exists():
            output_path.rename(temp_output)
        
        try:
            # Use ffmpeg to merge video and audio
            # We use the audio from the original video (audio_path)
            # and the video stream from our newly created silent video (temp_output)
            input_video = ffmpeg.input(str(temp_output))
            input_audio = ffmpeg.input(str(audio_path))
            
            (
                ffmpeg
                .output(
                    input_video.video,
                    input_audio.audio,
                    str(output_path),
                    vcodec='copy',
                    acodec='aac',
                    audio_bitrate='192k'
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            # Clean up temp file
            if temp_output.exists():
                temp_output.unlink()
            logger.info("Audio merge complete")
                
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error merging audio: {error_msg}")
            # If merging fails, restore the silent video
            if temp_output.exists():
                temp_output.rename(output_path)

def process_video(
    video_path: Path, 
    output_path: Path, 
    blur_type: str = "faces", 
    blur_strength: int = 30,
    blur_shape: str = "rect",
    blur_style: str = "smooth",
    progress_callback: Callable[[float], None] = None
):
    """
    Process a video by extracting frames, applying blur, and reassembling.
    
    Args:
        video_path: Path to input video
        output_path: Path to output video
        blur_type: Type of blur ('faces', 'background', etc.)
        blur_strength: Strength of blur
        blur_shape: Shape of blur
        blur_style: Style of blur
        progress_callback: Optional callback for progress updates (0.0 to 1.0)
    """
    # Create temp directory for frames
    temp_dir = video_path.parent / f"temp_{video_path.stem}"
    frames_in_dir = temp_dir / "in"
    frames_out_dir = temp_dir / "out"
    
    try:
        # 1. Extract frames
        if progress_callback: progress_callback(0.1)
        frame_paths, fps = extract_frames(video_path, frames_in_dir)
        
        frames_out_dir.mkdir(exist_ok=True, parents=True)
        
        # 2. Process frames
        effective_shape = "sam2" if blur_type == "faces" else blur_shape

        if blur_type == "faces" and effective_shape == "sam2" and image_processor.SAM2_AVAILABLE:
            logger.info("Using SAM2 Video Processing Pipeline")
            if progress_callback: progress_callback(0.2)
            
            image_processor.process_video_with_sam2(
                frames_in_dir,
                frames_out_dir,
                strength=blur_strength,
                style=blur_style
            )
            
            if progress_callback: progress_callback(0.8)
        else:
            # Legacy frame-by-frame loop
            total_frames = len(frame_paths)
            for i, frame_path in enumerate(frame_paths):
                output_frame_path = frames_out_dir / frame_path.name
                
                if blur_type == "faces":
                    image_processor.blur_faces(
                        frame_path, 
                        output_frame_path, 
                        strength=blur_strength, 
                        shape=effective_shape, 
                        style=blur_style
                    )
                elif blur_type == "background":
                    # TODO: Implement SAM2 based background blurring
                    image_processor.blur_background(frame_path, output_frame_path)
                else:
                    image_processor.apply_gaussian_blur(frame_path, output_frame_path, strength=blur_strength)
                
                # Update progress
                if progress_callback:
                    # Progress from 0.2 to 0.8
                    progress = 0.2 + (0.6 * (i + 1) / total_frames)
                    progress_callback(progress)
        
        # 3. Reassemble
        if progress_callback: progress_callback(0.9)
        reassemble_video(frames_out_dir, output_path, fps, audio_path=video_path)
        
        if progress_callback: progress_callback(1.0)
        
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
