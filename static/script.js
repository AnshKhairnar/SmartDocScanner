const video = document.getElementById('webcam-feed');
const canvas = document.getElementById('capture-canvas');
const cameraSelect = document.getElementById('camera-select');
const captureBtn = document.getElementById('capture-btn');
const gallery = document.getElementById('gallery');
const emptyState = document.getElementById('empty-state');
const pageCountSpan = document.getElementById('page-count');
const captureMobileBtn = document.getElementById('capture-mobile-btn');
const compileBtn = document.getElementById('compile-btn');
const flashOverlay = document.getElementById('flash-overlay');
const filterBtns = document.querySelectorAll('.toggle-btn');

let currentStream = null;
let scannedImages = []; // List of filenames
let currentFilter = 'bw';

// --- Camera Setup ---

async function getCameras() {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(device => device.kind === 'videoinput');

        cameraSelect.innerHTML = '';
        videoDevices.forEach((device, index) => {
            const option = document.createElement('option');
            option.value = device.deviceId;
            option.text = device.label || `Camera ${index + 1}`;
            cameraSelect.appendChild(option);
        });

        if (videoDevices.length > 0) {
            startCamera(videoDevices[0].deviceId);
        } else {
            alert("No cameras found.");
        }
    } catch (err) {
        console.error("Error enumerating devices:", err);
        alert("Camera permission denied or not available.");
    }
}

async function startCamera(deviceId) {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                deviceId: deviceId ? { exact: deviceId } : undefined,
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        });
        video.srcObject = stream;
        currentStream = stream;
    } catch (err) {
        console.error("Error starting camera:", err);
    }
}

cameraSelect.addEventListener('change', (e) => {
    startCamera(e.target.value);
});

// --- Flip Camera ---
const flipBtn = document.getElementById('flip-btn');
let currentDeviceIndex = 0;
let videoInputDevices = [];

async function updateDeviceList() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    videoInputDevices = devices.filter(device => device.kind === 'videoinput');
}

flipBtn.addEventListener('click', async () => {
    await updateDeviceList();
    if (videoInputDevices.length < 2) {
        showToast("Only one camera found", "info");
        return;
    }

    // Find next camera
    currentDeviceIndex = (currentDeviceIndex + 1) % videoInputDevices.length;
    const nextDeviceId = videoInputDevices[currentDeviceIndex].deviceId;

    // Update select dropdown
    cameraSelect.value = nextDeviceId;
    startCamera(nextDeviceId);
});

// --- Filter Selection ---
filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
    });
});

// --- Capture & Process ---

captureBtn.addEventListener('click', async () => {
    // Visual Flash
    flashOverlay.style.transition = 'none';
    flashOverlay.style.opacity = 0.8;
    setTimeout(() => {
        flashOverlay.style.transition = 'opacity 0.5s ease-out';
        flashOverlay.style.opacity = 0;
    }, 50);

    // Capture Frame to Canvas
    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const base64Image = canvas.toDataURL('image/jpeg', 0.9);

    // Show loading state on button
    const originalText = captureBtn.innerHTML;
    captureBtn.innerHTML = '<ion-icon name="hourglass"></ion-icon> Processing...';
    captureBtn.disabled = true;

    try {
        const response = await fetch('/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: base64Image,
                filter: currentFilter
            })
        });

        const result = await response.json();

        if (result.success) {
            addScanToGallery(result);
            if (!result.detected) {
                showToast("No document detected - saved full frame", "warning");
            } else {
                showToast("Document scanned successfully!", "success");
            }
        } else {
            showToast("Processing failed: " + result.error, "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Server error", "error");
    } finally {
        captureBtn.innerHTML = originalText;
        captureBtn.disabled = false;
    }
});

captureMobileBtn.addEventListener('click', () => {
    captureBtn.click();
});

function addScanToGallery(scanData) {
    scannedImages.push(scanData.filename);
    updateStats();

    // Create thumbnail
    const div = document.createElement('div');
    div.className = 'gallery-item';
    div.innerHTML = `
        <img src="${scanData.url}" alt="Scan">
        <button class="delete-btn" onclick="removeScan('${scanData.filename}', this)">
            <ion-icon name="trash"></ion-icon>
        </button>
    `;

    // Insert before empty state (or hide empty state)
    if (scannedImages.length === 1) {
        emptyState.style.display = 'none';
    }

    gallery.insertBefore(div, gallery.firstChild);
}

window.removeScan = function (filename, btnElement) {
    scannedImages = scannedImages.filter(f => f !== filename);
    btnElement.parentElement.remove();
    updateStats();

    if (scannedImages.length === 0) {
        emptyState.style.display = 'flex';
    }
};

function updateStats() {
    pageCountSpan.innerText = scannedImages.length;
    compileBtn.disabled = scannedImages.length === 0;
}

// --- Compile PDF ---

compileBtn.addEventListener('click', async () => {
    compileBtn.innerHTML = '<ion-icon name="sync"></ion-icon> Compiling...';
    compileBtn.disabled = true;

    try {
        const response = await fetch('/compile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames: scannedImages })
        });

        const result = await response.json();

        if (result.success) {
            window.location.href = result.download_url;
            showToast("PDF Downloaded!", "success");
        } else {
            showToast("Compilation error", "error");
        }
    } catch (err) {
        showToast("Server error", "error");
    } finally {
        compileBtn.innerHTML = '<ion-icon name="document-text"></ion-icon> Download PDF';
        compileBtn.disabled = false;
    }
});

// --- Toast Notification Helper ---
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.backgroundColor = type === 'error' ? '#ef4444' : (type === 'success' ? '#10b981' : '#334155');
    toast.style.color = 'white';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 4px 6px rgba(0,0,0,0.3)';
    toast.style.zIndex = '1000';
    toast.style.fontFamily = 'Inter, sans-serif';
    toast.style.animation = 'slideIn 0.3s ease-out';
    toast.innerText = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Init
getCameras();
