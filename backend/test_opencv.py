import cv2
import os

print(f"cv2.data.haarcascades: {cv2.data.haarcascades}")
xml_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
print(f"XML Path: {xml_path}")
print(f"Exists: {os.path.exists(xml_path)}")

try:
    face_cascade = cv2.CascadeClassifier(xml_path)
    print(f"Loaded: {not face_cascade.empty()}")
except Exception as e:
    print(f"Error: {e}")
