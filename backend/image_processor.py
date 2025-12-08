"""
Image processing module for BlurAI.
This module provides basic blur functionality using PIL and OpenCV.
In the future, this will integrate with SAM2 for segmentation-based blurring.
"""

from PIL import Image, ImageFilter
import cv2
import numpy as np
from pathlib import Path
import torch
from utils.logger import logger

# SAM2 Imports
try:
    from sam2.build_sam import build_sam2, build_sam2_video_predictor
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False
    logger.warning("SAM2 not available. Advanced segmentation will be disabled.")

# Global SAM2 model
sam2_predictor = None
sam2_video_predictor = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# Use Tiny model for speed on CPU
CHECKPOINT_PATH = Path("checkpoints/sam2.1_hiera_tiny.pt")
CONFIG_PATH = "configs/sam2.1/sam2.1_hiera_t.yaml"

def load_sam2_model():
    """Lazy load the SAM2 image model."""
    global sam2_predictor
    if sam2_predictor is not None:
        return sam2_predictor
    
    if not SAM2_AVAILABLE:
        logger.error("Attempted to load SAM2 but library is not installed.")
        raise RuntimeError("SAM2 library not installed.")
        
    if not CHECKPOINT_PATH.exists():
        logger.error(f"SAM2 checkpoint not found at {CHECKPOINT_PATH}")
        raise RuntimeError(f"SAM2 checkpoint not found at {CHECKPOINT_PATH}")

    logger.info(f"Loading SAM2 Image model on {DEVICE}...")
    sam2_model = build_sam2(CONFIG_PATH, str(CHECKPOINT_PATH), device=DEVICE)
    sam2_predictor = SAM2ImagePredictor(sam2_model)
    logger.info("SAM2 Image model loaded successfully.")
    return sam2_predictor

def load_sam2_video_model():
    """Lazy load the SAM2 video model."""
    global sam2_video_predictor
    if sam2_video_predictor is not None:
        return sam2_video_predictor
    
    if not SAM2_AVAILABLE:
        raise RuntimeError("SAM2 library not installed.")
        
    logger.info(f"Loading SAM2 Video model on {DEVICE}...")
    sam2_video_predictor = build_sam2_video_predictor(CONFIG_PATH, str(CHECKPOINT_PATH), device=DEVICE)
    logger.info("SAM2 Video model loaded successfully.")
    return sam2_video_predictor


def apply_gaussian_blur(image_path: Path, output_path: Path, strength: int = 15) -> Path:
    """
    Apply a simple Gaussian blur to the entire image.
    
    Args:
        image_path: Path to the input image
        output_path: Path where the blurred image will be saved
        strength: Blur strength (radius)
    
    Returns:
        Path to the blurred image
    """
    img = Image.open(image_path)
    blurred = img.filter(ImageFilter.GaussianBlur(radius=strength))
    blurred.save(output_path)
    return output_path


def blur_background(image_path: Path, output_path: Path) -> Path:
    """
    Blur the background of an image (everything EXCEPT the faces).
    Uses OpenCV's Haar Cascade for face detection.
    
    Args:
        image_path: Path to the input image
        output_path: Path where the processed image will be saved
    
    Returns:
        Path to the processed image
    """
    # Load the image using numpy to handle unicode paths
    with open(image_path, "rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    if img is None:
        # Fallback to simple blur if load fails
        return apply_gaussian_blur(image_path, output_path, strength=20)

    # Create a blurred version of the entire image
    blurred_img = cv2.GaussianBlur(img, (0, 0), 20)
    
    # Load the cascade
    cascade_filename = 'haarcascade_frontalface_default.xml'
    system_cascade_path = Path(cv2.data.haarcascades) / cascade_filename
    local_cascade_path = Path(cascade_filename)
    
    if not local_cascade_path.exists():
        import shutil
        shutil.copy(system_cascade_path, local_cascade_path)
        
    face_cascade = cv2.CascadeClassifier(str(local_cascade_path))
    
    if face_cascade.empty():
        # Fallback to simple blur if cascade fails
        cv2.imwrite(str(output_path), blurred_img)
        return output_path
    
    # Detect faces
    faces = face_cascade.detectMultiScale(
        cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    # For each face, copy the original (sharp) face back onto the blurred image
    for (x, y, w, h) in faces:
        # Create an oval mask for the face to blend it smoothly
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        axes = (w // 2, int(h // 1.6))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
        
        # Soften the mask
        mask = cv2.GaussianBlur(mask, (21, 21), 10)
        mask_3c = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
        
        # Extract regions
        face_region_sharp = img[y:y+h, x:x+w].astype(np.float32)
        face_region_blurred = blurred_img[y:y+h, x:x+w].astype(np.float32)
        
        # Blend: Sharp face where mask is white, blurred background where mask is black
        blended = (face_region_sharp * mask_3c) + (face_region_blurred * (1.0 - mask_3c))
        blurred_img[y:y+h, x:x+w] = blended.astype(np.uint8)
    
    # Save the result
    is_success, im_buf_arr = cv2.imencode(".jpg", blurred_img)
    if is_success:
        with open(output_path, "wb") as f:
            im_buf_arr.tofile(f)
    else:
        raise RuntimeError("Failed to encode output image")
        
    return output_path


def blur_faces(image_path: Path, output_path: Path, strength: int = 30, shape: str = "rect", style: str = "smooth") -> Path:
    """
    Detect and blur faces in an image.
    Uses OpenCV's Haar Cascade for face detection.
    TODO: Integrate with SAM2 for better face segmentation.
    
    Args:
        image_path: Path to the input image
        output_path: Path where the processed image will be saved
        strength: Blur strength (sigma for Gaussian blur or pixel size for pixelation)
        shape: Shape of the blur ('rect', 'oval', 'trace')
        style: Style of the blur ('smooth', 'pixelate')
    
    Returns:
        Path to the processed image
    """
    if shape == "sam2" and SAM2_AVAILABLE:
        return segment_and_blur_with_sam2(image_path, output_path, strength, style)

    # Load the image using numpy to handle unicode paths
    # cv2.imread fails with non-ASCII paths on Windows
    with open(image_path, "rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    if img is None:
        raise ValueError(f"Failed to load image from {image_path}")

    # Convert to RGB (OpenCV uses BGR)
    # img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # Not needed for detection/blurring logic here
    
    # Load the cascade
    # Handle potential unicode path issues by copying to a local file
    cascade_filename = 'haarcascade_frontalface_default.xml'
    system_cascade_path = Path(cv2.data.haarcascades) / cascade_filename
    local_cascade_path = Path(cascade_filename)
    
    if not local_cascade_path.exists():
        import shutil
        shutil.copy(system_cascade_path, local_cascade_path)
        
    face_cascade = cv2.CascadeClassifier(str(local_cascade_path))
    
    if face_cascade.empty():
        # Try absolute path as fallback
        face_cascade = cv2.CascadeClassifier(str(system_cascade_path))
        if face_cascade.empty():
            raise RuntimeError("Failed to load face cascade classifier")
    
    # Detect faces
    faces = face_cascade.detectMultiScale(
        cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    # Blur each detected face
    for (x, y, w, h) in faces:
        # Extract the face region
        face_region = img[y:y+h, x:x+w]
        
        # Apply Blur based on style
        if style == "pixelate":
            # Pixelate effect
            # Calculate pixel size based on strength (1-100)
            # Strength 1 -> 1 block (no change)
            # Strength 100 -> 20x20 blocks
            pixel_size = max(1, int(strength / 5))
            if pixel_size > 1:
                h_face, w_face = face_region.shape[:2]
                # Resize down
                small = cv2.resize(face_region, (max(1, w_face//pixel_size), max(1, h_face//pixel_size)), interpolation=cv2.INTER_LINEAR)
                # Resize up
                blurred_face = cv2.resize(small, (w_face, h_face), interpolation=cv2.INTER_NEAREST)
            else:
                blurred_face = face_region.copy()
        else:
            # Smooth (Gaussian) effect
            # Map 1-100 strength to 1-100 sigma for stronger blur
            sigma = max(1, strength)
            blurred_face = cv2.GaussianBlur(face_region, (0, 0), sigma)
        
        if shape == "oval":
            # Create an oval mask
            mask = np.zeros((h, w), dtype=np.uint8)
            center = (w // 2, h // 2)
            axes = (w // 2, int(h // 1.6)) # Slightly taller oval for faces
            cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
            
            # Soften the mask edges for better blending
            mask = cv2.GaussianBlur(mask, (21, 21), 10)
            
            # Convert mask to 3 channels float
            mask_3c = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
            
            face_float = face_region.astype(np.float32)
            blurred_float = blurred_face.astype(np.float32)
            
            # Blend
            blended = (blurred_float * mask_3c) + (face_float * (1.0 - mask_3c))
            img[y:y+h, x:x+w] = blended.astype(np.uint8)
            
        elif shape == "trace":
            # Use GrabCut for smart segmentation
            # 1. Create a mask initialized with zeros (background)
            mask = np.zeros(face_region.shape[:2], np.uint8)
            
            # 2. Initialize mask with an oval as "Probable Foreground"
            # This tells GrabCut: "The stuff in the middle is likely the face, the corners are likely background"
            h, w = face_region.shape[:2]
            center = (w // 2, h // 2)
            axes = (int(w * 0.4), int(h * 0.5)) # 40% width, 50% height oval
            cv2.ellipse(mask, center, axes, 0, 0, 360, cv2.GC_PR_FGD, -1)
            
            # 3. Run GrabCut
            bgdModel = np.zeros((1, 65), np.float64)
            fgdModel = np.zeros((1, 65), np.float64)
            
            # We use GC_INIT_WITH_MASK because we set up the mask manually
            try:
                cv2.grabCut(face_region, mask, None, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_MASK)
            except:
                pass # Fallback to the oval we drew if it fails

            # 4. Extract final mask (Foreground + Probable Foreground)
            # 0=BGD, 1=FGD, 2=PR_BGD, 3=PR_FGD
            mask2 = np.where((mask==2)|(mask==0), 0, 1).astype('uint8')
            
            # 5. Soften the mask edges significantly
            mask2 = cv2.GaussianBlur(mask2 * 255, (41, 41), 20)
            
            # Convert mask to 3 channels float
            mask_3c = cv2.cvtColor(mask2, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
            
            face_float = face_region.astype(np.float32)
            blurred_float = blurred_face.astype(np.float32)
            
            # Blend
            blended = (blurred_float * mask_3c) + (face_float * (1.0 - mask_3c))
            img[y:y+h, x:x+w] = blended.astype(np.uint8)

        else:
            # Default rectangular blur
            img[y:y+h, x:x+w] = blurred_face
    
    # Save the result using imencode to handle unicode paths
    is_success, im_buf_arr = cv2.imencode(".jpg", img)
    if is_success:
        with open(output_path, "wb") as f:
            im_buf_arr.tofile(f)
    else:
        raise RuntimeError("Failed to encode output image")
        
    return output_path


def blur_with_mask(image_path: Path, mask_path: Path, output_path: Path) -> Path:
    """
    Blur the image using a provided mask.
    The mask is expected to be a black and white image where white = blur, black = keep.
    
    Args:
        image_path: Path to the input image
        mask_path: Path to the mask image
        output_path: Path where the processed image will be saved
    
    Returns:
        Path to the processed image
    """
    # Load image and mask
    img = cv2.imread(str(image_path))
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    
    if img is None or mask is None:
        raise ValueError("Could not load image or mask")
        
    # Resize mask to match image size
    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]))
        
    # Create a blurred version of the entire image
    blurred_img = cv2.GaussianBlur(img, (51, 51), 30)
    
    # Convert mask to 3 channels to match image
    mask_3c = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    
    # Normalize mask to 0-1 range
    mask_normalized = mask_3c / 255.0
    
    # Blend: result = blurred * mask + original * (1 - mask)
    result = (blurred_img * mask_normalized + img * (1 - mask_normalized)).astype(np.uint8)
    
    cv2.imwrite(str(output_path), result)
    return output_path


def segment_and_blur_with_sam2(image_path: Path, output_path: Path, strength: int = 30, style: str = "smooth") -> Path:
    """
    Use SAM2 to segment faces/objects and blur them.
    Currently uses face detection to provide box prompts to SAM2.
    """
    # Load image
    with open(image_path, "rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
    if img is None:
        raise ValueError(f"Failed to load image from {image_path}")

    # Detect faces for prompts
    cascade_filename = 'haarcascade_frontalface_default.xml'
    local_cascade_path = Path(cascade_filename)
    if not local_cascade_path.exists():
        shutil.copy(Path(cv2.data.haarcascades) / cascade_filename, local_cascade_path)
        
    face_cascade = cv2.CascadeClassifier(str(local_cascade_path))
    faces = face_cascade.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(30, 30))
    
    if len(faces) == 0:
        # No faces found, return original
        cv2.imwrite(str(output_path), img)
        return output_path

    # Load SAM2
    predictor = load_sam2_model()
    
    # SAM2 expects RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    predictor.set_image(img_rgb)
    
    # Create a combined mask for all faces
    full_mask = np.zeros(img.shape[:2], dtype=np.uint8)
    
    for (x, y, w, h) in faces:
        # Box prompt: [x_min, y_min, x_max, y_max]
        box = np.array([x, y, x+w, y+h])
        
        # Predict mask
        masks, scores, _ = predictor.predict(
            point_coords=None,
            point_labels=None,
            box=box[None, :],
            multimask_output=False
        )
        
        # Add to full mask (masks[0] is the best mask)
        # SAM2 returns boolean mask, convert to uint8
        mask_uint8 = (masks[0] * 255).astype(np.uint8)
        full_mask = cv2.bitwise_or(full_mask, mask_uint8)

    # Apply blur using the generated mask
    # 1. Create blurred image
    if style == "pixelate":
        pixel_size = max(1, int(strength / 5))
        h_img, w_img = img.shape[:2]
        small = cv2.resize(img, (max(1, w_img//pixel_size), max(1, h_img//pixel_size)), interpolation=cv2.INTER_LINEAR)
        blurred_img = cv2.resize(small, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
    else:
        sigma = max(1, strength)
        blurred_img = cv2.GaussianBlur(img, (0, 0), sigma)
        
    # 2. Blend
    # Soften mask edges
    full_mask = cv2.GaussianBlur(full_mask, (11, 11), 5)
    mask_3c = cv2.cvtColor(full_mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
    
    img_float = img.astype(np.float32)
    blurred_float = blurred_img.astype(np.float32)
    
    result = (blurred_float * mask_3c) + (img_float * (1.0 - mask_3c))
    
    # Save
    cv2.imwrite(str(output_path), result.astype(np.uint8))
    return output_path
    return output_path


def blur_object(image_path: Path, output_path: Path, bbox: tuple = None) -> Path:
    """
    Blur a specific object in an image based on bounding box.
    TODO: Integrate with SAM2 for precise object segmentation.
    
    Args:
        image_path: Path to the input image
        output_path: Path where the processed image will be saved
        bbox: Bounding box as (x, y, width, height)
    
    Returns:
        Path to the processed image
    """
    if bbox is None:
        # If no bbox provided, just blur the entire image
        return apply_gaussian_blur(image_path, output_path)
    
    img = cv2.imread(str(image_path))
    x, y, w, h = bbox
    
    # Extract the region
    region = img[y:y+h, x:x+w]
    
    # Blur the region
    blurred_region = cv2.GaussianBlur(region, (99, 99), 30)
    
    # Replace the region
    img[y:y+h, x:x+w] = blurred_region
    
    # Save the result
    cv2.imwrite(str(output_path), img)
    return output_path


def process_video_with_sam2(frame_dir: Path, output_dir: Path, strength: int = 30, style: str = "smooth"):
    """
    Process an entire video (frame directory) using SAM2's video capabilities.
    1. Detects faces in the first frame.
    2. Prompts SAM2 with those faces.
    3. Propagates the masks through the entire video.
    4. Blurs the frames based on the masks.
    """
    if not SAM2_AVAILABLE:
        raise RuntimeError("SAM2 not available")

    logger.info(f"Starting SAM2 Video Processing on {frame_dir}")
    
    # 1. Initialize Predictor
    predictor = load_sam2_video_model()
    # Use offload_video_to_cpu=True and async_loading_frames=True to save memory
    inference_state = predictor.init_state(
        video_path=str(frame_dir),
        offload_video_to_cpu=True,
        async_loading_frames=True
    )
    
    # 2. Detect faces in Frame 0 for prompting
    # We need to find the first frame file
    frames = sorted(list(frame_dir.glob("*.jpg")))
    if not frames:
        raise ValueError("No frames found")
        
    first_frame_path = frames[0]
    
    # Use existing face detection logic
    # Load image
    with open(first_frame_path, "rb") as f:
        file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        img_0 = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
    cascade_filename = 'haarcascade_frontalface_default.xml'
    local_cascade_path = Path(cascade_filename)
    if not local_cascade_path.exists():
        import shutil
        shutil.copy(Path(cv2.data.haarcascades) / cascade_filename, local_cascade_path)
        
    face_cascade = cv2.CascadeClassifier(str(local_cascade_path))
    faces = face_cascade.detectMultiScale(cv2.cvtColor(img_0, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(30, 30))
    
    if len(faces) == 0:
        logger.warning("No faces detected in the first frame. Skipping SAM2 processing.")
        # Just copy frames to output
        import shutil
        for frame in frames:
            shutil.copy(frame, output_dir / frame.name)
        return

    logger.info(f"Detected {len(faces)} faces in the first frame. Adding prompts...")
    
    # 3. Add Prompts (Box) for each face
    for i, (x, y, w, h) in enumerate(faces):
        # SAM2 expects box as [x1, y1, x2, y2]
        box = np.array([x, y, x+w, y+h], dtype=np.float32)
        
        # Add new points/box
        # obj_id is just an integer ID for the object
        _, out_obj_ids, out_mask_logits = predictor.add_new_points_or_box(
            inference_state=inference_state,
            frame_idx=0,
            obj_id=i,
            box=box
        )
    
    # 4. Propagate through video
    logger.info("Propagating masks through video...")
    
    # We need to map frame index to frame path
    frame_map = {i: p for i, p in enumerate(frames)}
    
    for out_frame_idx, out_obj_ids, out_mask_logits in predictor.propagate_in_video(inference_state):
        # out_mask_logits is [N_objects, 1, H, W]
        
        current_frame_path = frame_map[out_frame_idx]
        output_frame_path = output_dir / current_frame_path.name
        
        # Load original frame
        with open(current_frame_path, "rb") as f:
            file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
        # Combine masks for all objects
        full_mask = np.zeros(img.shape[:2], dtype=np.uint8)
        
        for i, obj_id in enumerate(out_obj_ids):
            # Get mask for this object
            mask_logit = out_mask_logits[i, 0] # [H, W]
            mask = (mask_logit > 0.0).cpu().numpy().astype(np.uint8) * 255
            full_mask = cv2.bitwise_or(full_mask, mask)
            
        # Apply Blur
        if style == "pixelate":
            pixel_size = max(1, int(strength / 5))
            h_img, w_img = img.shape[:2]
            small = cv2.resize(img, (max(1, w_img//pixel_size), max(1, h_img//pixel_size)), interpolation=cv2.INTER_LINEAR)
            blurred_img = cv2.resize(small, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
        else:
            sigma = max(1, strength)
            blurred_img = cv2.GaussianBlur(img, (0, 0), sigma)
            
        # Blend
        full_mask = cv2.GaussianBlur(full_mask, (11, 11), 5)
        mask_3c = cv2.cvtColor(full_mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
        
        img_float = img.astype(np.float32)
        blurred_float = blurred_img.astype(np.float32)
        
        result = (blurred_float * mask_3c) + (img_float * (1.0 - mask_3c))
        
        cv2.imwrite(str(output_frame_path), result.astype(np.uint8))
        
    logger.info("SAM2 Video Processing Complete.")
