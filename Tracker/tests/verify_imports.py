import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Verifying imports...")
try:
    from src.core.config import cfg
    print("[OK] Config")
    from src.hardware.camera import Camera
    print("[OK] Camera")
    from src.hardware.gimbal import GimbalController
    print("[OK] GimbalController")
    from src.detection.detector import HailoDetector
    print("[OK] HailoDetector")
    from src.detection.tracker import ObjectTracker
    print("[OK] ObjectTracker")
    from src.core.app import TrackingApp
    print("[OK] TrackingApp")
    from src.api.server import app
    print("[OK] FastAPI App")
    
    print("\nAll modules imported successfully.")
except ImportError as e:
    print(f"\n[FAIL] Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n[FAIL] Exception: {e}")
    sys.exit(1)
