import cv2
import numpy as np

class DocumentScanner:
    def __init__(self):
        pass

    def detect_document(self, frame):
        """
        Detects the largest quadrilateral in the frame.
        Returns the contour of the document and the processed frame (for debug).
        """
        # 1. Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 2. Blur to remove noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 3. Edge Detection
        edged = cv2.Canny(blurred, 75, 200)
        
        # 4. Find Contours
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        doc_contour = None
        
        for c in contours:
            # Approximate the contour
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            
            # If our approximated contour has 4 points, we can assume we found the screen/paper
            if len(approx) == 4:
                doc_contour = approx
                break
                
        return doc_contour, edged

    def get_perspective_transform(self, image, pts):
        """
        Unwarps the detected document to a flat top-down view.
        """
        # Order points: top-left, top-right, bottom-right, bottom-left
        rect = self.order_points(pts.reshape(4, 2))
        (tl, tr, br, bl) = rect

        # Compute width of new image
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        # Compute height of new image
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Construct destination points
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        # Compute perspective transform matrix
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        return warped

    def order_points(self, pts):
        """
        Orders coordinates: top-left, top-right, bottom-right, bottom-left
        """
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)] # Top-left has smallest sum
        rect[2] = pts[np.argmax(s)] # Bottom-right has largest sum
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)] # Top-right has smallest difference
        rect[3] = pts[np.argmax(diff)] # Bottom-left has largest difference
        
        return rect

    def apply_filter(self, image, filter_type="bw"):
        """
        Applies filters to look like a scan.
        """
        if filter_type == "bw":
            # Adaptive thresholding for "Xerox" look
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # T = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)[1] # Simple
            T = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            return T
        elif filter_type == "gray":
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            return image
