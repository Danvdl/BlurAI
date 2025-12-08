try:
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    print("SAM2 imports successful")
except ImportError as e:
    print(f"SAM2 import failed: {e}")
