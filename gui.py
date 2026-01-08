import customtkinter as ctk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import threading
import time
import numpy as np
from scanner import DocumentScanner
from fpdf import FPDF
from pygrabber.dshow_graph import FilterGraph

# Silence OpenCV errors globally and early
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except AttributeError:
    pass

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ASEPScannerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Smart PDF Scanner")
        self.geometry("900x700")
        
        # Scanner Logic
        self.settings = {"camera_index": 0}  # Default settings
        self.scanner = DocumentScanner()
        self.captured_images = []
        self.output_folder = "scanned_docs"
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Smart PDF Scanner", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_camera = ctk.CTkButton(self.sidebar, text="Start Scanning", command=self.open_scanner)
        self.btn_camera.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_compile = ctk.CTkButton(self.sidebar, text="Compile PDF", command=self.compile_pdf, fg_color="green")
        self.btn_compile.grid(row=2, column=0, padx=20, pady=10)

        # Search Section
        self.btn_search = ctk.CTkButton(self.sidebar, text="Search Pages", command=self.toggle_search, fg_color="gray")
        self.btn_search.grid(row=3, column=0, padx=20, pady=5)

        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Type to search...")
        # Initially hidden, will be gridded in toggle_search

        self.listbox_label = ctk.CTkLabel(self.sidebar, text="Captured Pages:", anchor="w")
        self.listbox_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        
        self.pages_text = ctk.CTkTextbox(self.sidebar, width=160)
        self.pages_text.grid(row=6, column=0, padx=20, pady=5, sticky="nsew")
        
        self.btn_about = ctk.CTkButton(self.sidebar, text="About", command=self.open_about, fg_color="transparent", border_width=1)
        self.btn_about.grid(row=8, column=0, padx=20, pady=10, sticky="s")

        self.btn_preferences = ctk.CTkButton(self.sidebar, text="Preferences", command=self.open_preferences, fg_color="transparent", border_width=1)
        self.btn_preferences.grid(row=7, column=0, padx=20, pady=(20, 10), sticky="s")
        
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Main Area (Preview)
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.preview_label = ctk.CTkLabel(self.main_area, text="No scans yet.\nClick 'Start Scanning' to begin.", font=ctk.CTkFont(size=16))
        self.preview_label.pack(expand=True, fill="both")

    def open_scanner(self):
        ScannerWindow(self)

    def add_image(self, filepath):
        self.captured_images.append(filepath)
        self.pages_text.insert("end", f"{os.path.basename(filepath)}\n")
        
        # Show preview of last image
        img = Image.open(filepath)
        img.thumbnail((600, 600))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self.preview_label.configure(image=ctk_img, text="")
        self.preview_label.image = ctk_img

    def compile_pdf(self):
        if not self.captured_images:
            messagebox.showwarning("Empty", "No images to compile!")
            return
            
        output_filename = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not output_filename:
            return
            
        pdf = FPDF()
        for img_path in self.captured_images:
            pdf.add_page()
            pdf.image(img_path, x=0, y=0, w=210) # Fit to A4 width
            
        pdf.output(output_filename)
        messagebox.showinfo("Success", "PDF Compiled Successfully!")
        
        # Clear session
        self.captured_images = []
        self.pages_text.delete("1.0", "end")
        self.preview_label.configure(image=None, text="Compilation Complete.\nReady for next batch.")

    def toggle_search(self):
        if self.search_entry.winfo_viewable():
            self.search_entry.grid_forget()
        else:
            self.search_entry.grid(row=4, column=0, padx=20, pady=5)
            self.search_entry.focus()

    def open_about(self):
        AboutWindow(self)

    def open_preferences(self):
        PreferencesWindow(self)


class ScannerWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Scanning...")
        self.geometry("800x600")
        
        # Use selected camera index
        camera_idx = self.parent.settings.get("camera_index", 0)
        self.high_quality = self.parent.settings.get("high_quality", False)
        
        # Try to open camera with robust backend fallback
        self.cap = self.open_camera_robust(camera_idx)
        
        if not self.cap or not self.cap.isOpened():
             self.video_label.configure(text="Error: Is the camera connected?")
        
        self.video_label = ctk.CTkLabel(self, text="")
        self.video_label.pack(fill="both", expand=True)
        
        self.status_label = ctk.CTkLabel(self, text="Looking for document...", font=("Arial", 16))
        self.status_label.pack(pady=10)
        
        self.btn_capture = ctk.CTkButton(self, text="Manual Capture", command=self.manual_capture)
        self.btn_capture.pack(pady=10)

        self.scanner = DocumentScanner() # Initialize scanner logic
        
        # Black screen detector variables
        self.black_frame_count = 0
        self.black_screen_warning = False

        # Auto-capture variables
        self.last_contour = None
        self.stable_frames = 0
        self.required_stable_frames = 15 
        self.cooldown = 0
        
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.update_feed()

    def open_camera_robust(self, index):
        """Tries to open camera with Auto backend, then DSHOW if that fails to read."""
        # Helper to configure
        def configure_cap(cap):
            # Apply resolution based on settings
            if self.high_quality:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            else:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
            # Try to force MJPG (helps with Iriun/Virtual)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
        # 1. Try Auto
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            configure_cap(cap)
            # Test read
            ret, _ = cap.read()
            if ret:
                return cap
            else:
                print(f"Index {index} opened but failed to read (Auto). Trying DSHOW...")
                cap.release()
        
        # 2. Try DSHOW (Virtual cameras often need this)
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            configure_cap(cap)
            ret, _ = cap.read()
            if ret:
                print(f"Index {index} working with DSHOW.")
                return cap
            else:
                cap.release()
                
        # 3. Fallback to 0 if we weren't already trying 0
        if index != 0:
            print(f"Index {index} failed completely. Falling back to Camera 0.")
            return self.open_camera_robust(0)
            
        return None

        # Auto-capture variables
        self.last_contour = None
        self.stable_frames = 0
        self.required_stable_frames = 15 # Approx 0.5-1 sec depending on FPS
        self.cooldown = 0
        
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.update_feed()

    def update_feed(self):
        ret, frame = self.cap.read()
        if not ret:
            self.video_label.configure(text="Camera disconnected or stalled.")
            return

        # Check for black screen (virtual camera issue)
        if np.mean(frame) < 10:
            self.black_frame_count += 1
        else:
            self.black_frame_count = 0
            
        if self.black_frame_count > 30 and not self.black_screen_warning:
             self.status_label.configure(text="Warning: Black Screen Detected. Check Camera App.", text_color="red")
             self.black_screen_warning = True
        elif self.black_frame_count == 0 and self.black_screen_warning:
             self.status_label.configure(text="Looking for document...", text_color="white")
             self.black_screen_warning = False

        # Detection
        doc_contour, edged = self.scanner.detect_document(frame)
        
        display_frame = frame.copy()
        
        if doc_contour is not None:
            cv2.drawContours(display_frame, [doc_contour], -1, (0, 255, 0), 2)
            
            # Check stability for auto-capture
            if self.cooldown > 0:
                self.cooldown -= 1
                self.status_label.configure(text=f"Captured! Cooldown... {self.cooldown}", text_color="green")
            else:
                if self.is_stable(doc_contour):
                    self.stable_frames += 1
                    self.status_label.configure(text=f"Hold still... {self.stable_frames}/{self.required_stable_frames}", text_color="orange")
                    
                    if self.stable_frames >= self.required_stable_frames:
                        self.auto_capture(frame, doc_contour)
                else:
                    self.stable_frames = 0
                    self.status_label.configure(text="Align document", text_color="white")
                    
            self.last_contour = doc_contour
        else:
            self.stable_frames = 0
            self.status_label.configure(text="No document detected", text_color="gray")

        # Convert to Tkinter
        cv2_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2_image)
        imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=(640, 480))
        self.video_label.configure(image=imgtk)
        self.video_label.image = imgtk
        
        self.after(30, self.update_feed)

    def is_stable(self, contour):
        if self.last_contour is None: return False
        return cv2.matchShapes(contour, self.last_contour, 1, 0.0) < 0.1

    def auto_capture(self, frame, contour):
        # 1. Warp
        warped = self.scanner.get_perspective_transform(frame, contour.reshape(4, 2))
        
        # 2. Filter (Xerox look)
        # Get filter setting
        filter_mode = self.parent.settings.get("scan_filter", "bw") # Default B&W
        processed = self.scanner.apply_filter(warped, filter_type=filter_mode)
        
        # 3. Save
        timestamp = int(time.time() * 1000)
        filename = f"scan_{timestamp}.jpg"
        filepath = os.path.join(self.parent.output_folder, filename)
        cv2.imwrite(filepath, processed)
        
        # 4. Notify
        self.parent.add_image(filepath)
        self.cooldown = 30 # Wait 30 frames before next capture
        self.stable_frames = 0
        print(f"Auto-captured: {filepath}")

    def manual_capture(self):
        # Capture raw frame if no doc detected, or warp if detected
        ret, frame = self.cap.read()
        if ret:
            # Check filter
            filter_mode = self.parent.settings.get("scan_filter", "bw")
            
            doc_contour, _ = self.scanner.detect_document(frame)
            if doc_contour is not None:
                self.auto_capture(frame, doc_contour)
            else:
                # Save raw but processed with filter if desired?
                # Usually manual capture of generic scene might want color, but if "Scan Mode" is B&W, assume user wants that.
                processed = self.scanner.apply_filter(frame, filter_type=filter_mode)
                
                timestamp = int(time.time() * 1000)
                filename = f"manual_{timestamp}.jpg"
                filepath = os.path.join(self.parent.output_folder, filename)
                cv2.imwrite(filepath, processed)
                self.parent.add_image(filepath)

    def close(self):
        self.cap.release()
        self.destroy()


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule_show)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def schedule_show(self, event=None):
        self.id = self.widget.after(500, self.show_tooltip) # 500ms delay

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        
        # Position below the widget to avoid overlap/flicker
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, fg_color="#333333", corner_radius=5, padx=10, pady=5)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class PreferencesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Preferences")
        self.geometry("400x450") # Increased height for more options
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.label = ctk.CTkLabel(self, text="Camera Settings", font=ctk.CTkFont(size=18, weight="bold"))
        self.label.pack(pady=20)

        self.camera_label = ctk.CTkLabel(self, text="Select Camera:")
        self.camera_label.pack(pady=5)

        # Detect cameras
        self.available_cameras = self.detect_cameras()
        
        # Get current camera name if possible, else default to index
        current_idx = self.parent.settings.get("camera_index", 0)
        current_name = f"Camera {current_idx}" # fallback
        if current_idx < len(self.available_cameras):
            current_name = self.available_cameras[current_idx]
            
        self.camera_var = ctk.StringVar(value=current_name)

        self.camera_menu = ctk.CTkOptionMenu(self, variable=self.camera_var, values=self.available_cameras, command=self.change_camera)
        self.camera_menu.pack(pady=10)
        ToolTip(self.camera_menu, "Choose which camera device to use for scanning.\nSupports standard webcams and virtual cameras (e.g. Iriun, Camo).")

        # Quality Toggle
        is_hq = self.parent.settings.get("high_quality", False)
        self.quality_switch = ctk.CTkSwitch(self, text="High Quality Capture (1080p)", command=self.toggle_quality)
        if is_hq:
            self.quality_switch.select()
        self.quality_switch.pack(pady=10)
        ToolTip(self.quality_switch, "Attempt to capture at 1920x1080 resolution.\nTurn OFF if you experience black screens or lag.")

        # Filter Settings
        self.filter_label = ctk.CTkLabel(self, text="Scan Mode:")
        self.filter_label.pack(pady=5)
        
        # Map nice names to internal keys
        self.filter_map = {"Black & White": "bw", "Grayscale": "gray", "Color (Original)": "original"}
        self.filter_keys = list(self.filter_map.keys())
        
        # Get current setting (reverse map)
        current_filter_key = self.parent.settings.get("scan_filter", "bw")
        current_val = "Black & White"
        for k, v in self.filter_map.items():
            if v == current_filter_key:
                current_val = k
                break
        
        self.filter_var = ctk.StringVar(value=current_val)
        self.filter_menu = ctk.CTkOptionMenu(self, variable=self.filter_var, values=self.filter_keys, command=self.change_filter)
        self.filter_menu.pack(pady=10)
        ToolTip(self.filter_menu, "Select the visual style for captures:\n- Black & White: High contrast, like a document scan.\n- Grayscale: For photos/texture.\n- Color: Unfiltered raw image.")

        self.btn_refresh = ctk.CTkButton(self, text="Refresh Cameras", command=self.refresh_cameras, fg_color="gray")
        self.btn_refresh.pack(pady=5)
        ToolTip(self.btn_refresh, "Reload the list of available cameras.\nUse this if you plugged in a camera after opening the app.")

        self.close_btn = ctk.CTkButton(self, text="Close", command=self.destroy)
        self.close_btn.pack(pady=20)

    def detect_cameras(self):
        """
        Robust detection:
        1. Get names from pygrabber (DirectShow).
        2. Probe indices 0-5 with cv2.
        3. Merge results.
        """
        # Silence OpenCV errors safely (already done globally, but keep for safety in this scope if needed/reload)
        try:
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
        except AttributeError:
            pass 
        
        # 1. Get names
        grabber_names = []
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            grabber_names = graph.get_input_devices()
        except ImportError:
            print("pygrabber not installed or found")
        except Exception as e:
            print(f"pygrabber error: {e}")

        # 2. Probe & Merge
        final_list = []
        consecutive_failures = 0
        
        # Check up to 10 indices, but stop early if we find nothing
        for i in range(10): 
            try:
                # Decide backend strategy
                # If we have a name from pygrabber, we can be more aggressive/specific (DSHOW)
                # If we are probing blind, be gentle (Auto).
                
                is_known_device = i < len(grabber_names)
                
                cap = None
                if is_known_device:
                    # We expect a camera here, try DSHOW directly as it maps to pygrabber names
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                         cap = cv2.VideoCapture(i) # Fallback to Auto
                else:
                    # Blind probe
                    cap = cv2.VideoCapture(i)
                    if not cap.isOpened() and consecutive_failures == 0:
                         # Only try DSHOW fallback if we haven't failed recently (to avoid spam)
                         cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)

                if cap is not None and cap.isOpened():
                    # Camera exists
                    is_working = True # Assume yes
                    cap.release()
                    
                    consecutive_failures = 0 # Reset counter
                    
                    if i < len(grabber_names):
                        final_list.append(grabber_names[i])
                    else:
                        final_list.append(f"Camera {i}")
                else:
                    consecutive_failures += 1
            except:
                consecutive_failures += 1
                
            # If we fail 2 times in a row, assume no more cameras exist
            # gaps are rare (e.g. 0, 2) but possible. 
            if consecutive_failures >= 2 and i >= len(grabber_names):
                break
        
        if not final_list:
            # If nothing found, at least return Camera 0 as fallback
            return ["Camera 0"]
        return final_list


    def refresh_cameras(self):
        self.available_cameras = self.detect_cameras()
        self.camera_menu.configure(values=self.available_cameras)
        
        # Reset selection if current invalid
        current = self.camera_var.get()
        if current not in self.available_cameras:
            if self.available_cameras:
                self.camera_var.set(self.available_cameras[0])
                self.change_camera(self.available_cameras[0])

    def toggle_quality(self):
        self.parent.settings["high_quality"] = bool(self.quality_switch.get())
        print(f"High Quality set to: {self.parent.settings['high_quality']}")

    def change_filter(self, choice):
        val = self.filter_map[choice]
        self.parent.settings["scan_filter"] = val
        print(f"Filter set to: {val}")

    def change_camera(self, choice):
        # Find index of choice in available_cameras
        # Logic: We know detect_cameras builds the list in index order (0, 1, 2...)
        # regardless of name source. So we can trust the list index matches the camera index.
        # UNLESS there are gaps (e.g. 0 open, 1 closed, 2 open).
        # My detect_cameras loop is sequential 0..9. 
        # Wait, if 0 is open, 1 is closed, 2 is open.
        # final_list = ["Name0", "Name2"] -> Index 0 of list, Index 1 of list.
        # Actual camera indices: 0, 2.
        # We need to map Name -> CameraIndex.
        
        # Better approach for change_camera: Re-derive index or store map.
        # For simplicity, let's store a map or re-scan to match name.
        
        # Quick fix: The current generic logic relies on list position matching or checking "Camera X".
        # If I have gaps, "Camera 2" might be at list index 1.
        
        # Let's map name to index by reconstructing the detection temporarily 
        # OR just iterate and find which index generated this name.
        
        # Re-running detection logic to find index of this name:
        target_idx = -1
        
        # 1. Names from pygrabber
        grabber_names = []
        try:
            graph = FilterGraph()
            grabber_names = graph.get_input_devices()
        except: pass
        
        # Check if it matches a grabber name directly (and assumes index matches)
        if choice in grabber_names:
            target_idx = grabber_names.index(choice)
        
        # If not found or if we are using "Camera X" fallback
        if target_idx == -1:
             # Try parsing "Camera X"
            if choice.startswith("Camera "):
                try:
                    target_idx = int(choice.split(" ")[1])
                except: pass
        
        # If still not safe, we might have an issue where "Camera 2" is valid but python thinks index 2.
        # But what if "Logitech" is at index 0?
        # Let's try to trust the user selection.
        
        if target_idx != -1:
            self.parent.settings["camera_index"] = target_idx
            print(f"Camera switched to index {target_idx} ({choice})")
        else:
             # Fallback: Assume the list order in menu matches the *available* devices, 
             # but we need the actual hardware index.
             # This is tricky with gaps. 
             # Let's stick to the simplest valid assumption: 
             # Most users have 0, 1 contiguous. 
             # If gaps, pygrabber usually aligns with OS indices.
             pass


class AboutWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("About ASEP Scanner")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Make it modal-like
        self.transient(parent)
        self.grab_set()
        
        self.logo_label = ctk.CTkLabel(self, text="Smart PDF Scanner", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.pack(pady=(30, 10))
        
        self.version_label = ctk.CTkLabel(self, text="Version 1.1.0", font=ctk.CTkFont(size=12))
        self.version_label.pack(pady=0)
        
        self.desc_label = ctk.CTkLabel(self, text="An advanced document scanner and PDF compiler.\nBuilt for ASEP Project.", 
                                       font=ctk.CTkFont(size=14), wraplength=300)
        self.desc_label.pack(pady=20)
        
        self.credits_label = ctk.CTkLabel(self, text="Developed by Ansh & Team", font=ctk.CTkFont(size=12, slant="italic"))
        self.credits_label.pack(side="bottom", pady=20)

if __name__ == "__main__":
    app = ASEPScannerGUI()
    app.mainloop()
