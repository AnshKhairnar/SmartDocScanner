import os
import cv2
import numpy as np
import base64
import time
from flask import Flask, render_template, request, jsonify, send_file
from scanner import DocumentScanner
from fpdf import FPDF

# explicitly set folder paths
template_dir = os.path.abspath('templates')
static_dir = os.path.abspath('static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
scanner = DocumentScanner()

# Ensure directories exist
SCANS_DIR = os.path.join("static", "scans")
OUTPUT_DIR = os.path.join("static", "output")
os.makedirs(SCANS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process_image():
    try:
        # Get image from POST request (base64)
        data = request.json.get("image")
        filter_type = request.json.get("filter", "bw") # bw, gray, original
        
        if not data:
            return jsonify({"error": "No image data provided"}), 400

        # Decode base64
        header, encoded = data.split(",", 1)
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Detect Document
        doc_contour, _ = scanner.detect_document(frame)
        
        # Warp or use original
        if doc_contour is not None:
            processed_frame = scanner.get_perspective_transform(frame, doc_contour.reshape(4, 2))
            detected = True
        else:
            processed_frame = frame
            detected = False

        # Apply Filter
        final_image = scanner.apply_filter(processed_frame, filter_type=filter_type)

        # Save to file
        timestamp = int(time.time() * 1000)
        filename = f"scan_{timestamp}.jpg"
        filepath = os.path.join(SCANS_DIR, filename)
        cv2.imwrite(filepath, final_image)

        # Return info
        return jsonify({
            "success": True,
            "detected": detected,
            "url": f"/static/scans/{filename}",
            "filename": filename
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/compile", methods=["POST"])
def compile_pdf():
    try:
        filenames = request.json.get("filenames", [])
        if not filenames:
            return jsonify({"error": "No files to compile"}), 400

        pdf = FPDF()
        for fname in filenames:
            path = os.path.join(SCANS_DIR, fname)
            if os.path.exists(path):
                pdf.add_page()
                # A4 size 210x297mm
                pdf.image(path, x=0, y=0, w=210)
        
        timestamp = int(time.time())
        output_filename = f"Compiled_Doc_{timestamp}.pdf"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        pdf.output(output_path)

        return jsonify({
            "success": True,
            "download_url": f"/download_pdf/{output_filename}"
        })

    except Exception as e:
        print(f"Compile Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/download_pdf/<filename>")
def download_pdf(filename):
    return send_file(os.path.join(OUTPUT_DIR, filename), as_attachment=True)

@app.route("/cleanup", methods=["POST"])
def cleanup():
    # Optional: Clear temp files
    # For now, we won't delete automatically to allow history, but could add later
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
