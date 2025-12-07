"""
Image processing module for BlurAI.
This module provides basic blur functionality using PIL and OpenCV.
In the future, this will integrate with SAM2 for segmentation-based blurring.
"""

from PIL import Image, ImageFilter
import cv2
import numpy as np
from pathlib import Path


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
    Blur the background of an image.
    Currently applies a simple blur to the entire image.
    TODO: Integrate with SAM2 for proper background segmentation.
    
    Args:
        image_path: Path to the input image
        output_path: Path where the processed image will be saved
    
    Returns:
        Path to the processed image
    """
    # For now, just apply a strong blur to simulate background blur
    return apply_gaussian_blur(image_path, output_path, strength=20)


def blur_faces(image_path: Path, output_path: Path) -> Path:
    """
    Detect and blur faces in an image.
    Uses OpenCV's Haar Cascade for face detection.
    TODO: Integrate with SAM2 for better face segmentation.
    
    Args:
        image_path: Path to the input image
        output_path: Path where the processed image will be saved
    
    Returns:
        Path to the processed image
    """
    # Load the image
    img = cv2.imread(str(image_path))
    
    # Convert to RGB (OpenCV uses BGR)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Load the cascade
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    
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
        
        # Apply Gaussian blur to the face region
        blurred_face = cv2.GaussianBlur(face_region, (99, 99), 30)
        
        # Replace the face region with the blurred version
        img[y:y+h, x:x+w] = blurred_face
    
    # Save the result
    cv2.imwrite(str(output_path), img)
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
