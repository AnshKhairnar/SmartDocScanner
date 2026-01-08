import cv2
import time
import numpy as np

try:
    from pygrabber.dshow_graph import FilterGraph
    graph = FilterGraph()
    devices = graph.get_input_devices()
except:
    devices = []

print(f"Detected Devices (pygrabber): {devices}")

print("-" * 30)
print("Probing Indices 0-5...")

for i in range(5):
    print(f"\nChecking Index {i}...")
    
    # Test Auto
    print("  Backends to test: AUTO, DSHOW, MSMF")
    
    backends = [
        ("AUTO", cv2.CAP_ANY),
        ("DSHOW", cv2.CAP_DSHOW), 
        ("MSMF", cv2.CAP_MSMF)
    ]
    
    for name, backend in backends:
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            # Try to force standard res
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            ret, frame = cap.read()
            if ret:
                mean_val = np.mean(frame)
                status = "WORKING"
                if mean_val < 5:
                    status = "BLACK FRAME"
                print(f"  [{name}] SUCCESS. Resolution: {frame.shape[1]}x{frame.shape[0]}. Status: {status}")
            else:
                print(f"  [{name}] OPENED but NO FRAME.")
            cap.release()
        else:
            print(f"  [{name}] FAILED to open.")
            
print("\nDone.")
