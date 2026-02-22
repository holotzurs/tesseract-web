const droparea = document.querySelector(".controls-area");
const input = document.querySelector("#uploadimage");
const ocrImg = document.querySelector("#ocr-img");
const ocrPdf = document.querySelector("#ocr-pdf");
const ocrCanvas = document.querySelector("#ocr-canvas"); // Kept for future flexibility, currently hidden
const fileDisplayContainer = document.querySelector("#file-display-container");
const resultTextarea = document.querySelector("#resulttext");
const fileResizer = document.querySelector("#file-display-resizer");

// --- Custom Resize Logic ---
let isResizing = false;

fileResizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.body.style.cursor = 'ns-resize'; // Global cursor while resizing
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', () => {
        isResizing = false;
        document.body.style.cursor = 'default';
        document.removeEventListener('mousemove', handleMouseMove);
    });
});

function handleMouseMove(e) {
    if (!isResizing) return;
    const containerTop = fileDisplayContainer.getBoundingClientRect().top;
    const newHeight = e.clientY - containerTop;
    if (newHeight > 200) { // Minimum height
        fileDisplayContainer.style.height = newHeight + 'px';
        fileDisplayContainer.style.minHeight = newHeight + 'px'; // Ensure it sticks
    }
}

let state = {
    isDragging: false,
    wrongFile: false,
    file: null
};

// --- Core Display Functions ---
function resetVisualDisplay() {
    ocrImg.classList.add('hidden');
    ocrPdf.classList.add('hidden');
    ocrCanvas.classList.add('hidden');
    resultTextarea.value = ""; // Clear result text pane
}

function displayImage() {
    resetVisualDisplay();
    ocrImg.src = URL.createObjectURL(state.file);
    ocrImg.classList.remove('hidden');
    ocrCanvas.classList.add('hidden');
}

function displayPdf() {
    resetVisualDisplay();
    ocrPdf.src = URL.createObjectURL(state.file);
    ocrPdf.classList.remove('hidden');
    ocrCanvas.classList.add('hidden');
}

function drawOCRData(ocrDataArray, imageSrc) {
    if (!ocrDataArray || ocrDataArray.length === 0) return;
    
    // For now, we only visualize the first page if multiple pages are present (e.g. from PDF)
    // In a more advanced UI, we'd have page navigation.
    const pageData = ocrDataArray[0].ocr_data; 
    
    const img = new Image();
    img.onload = () => {
        ocrCanvas.width = img.width;
        ocrCanvas.height = img.height;
        const ctx = ocrCanvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 2;
        ctx.fillStyle = 'rgba(255, 0, 0, 0.1)';

        pageData.forEach(item => {
            // pytesseract.image_to_data returns many levels, 
            // level 5 is usually 'word'
            if (item.level === 5 && item.text && item.text.trim() !== '') {
                ctx.strokeRect(item.left, item.top, item.width, item.height);
                ctx.fillRect(item.left, item.top, item.width, item.height);
            }
        });
        
        ocrCanvas.classList.remove('hidden');
        ocrImg.classList.add('hidden');
        ocrPdf.classList.add('hidden');
    };
    img.src = imageSrc;
}

const onDrop = (file) => {
    resetVisualDisplay(); // Always reset on new file selection
    if (file.type.indexOf("image/") >= 0) {
        state.file = file;
        displayImage();
    } else if (file.type.indexOf("application/pdf") >= 0) {
        state.file = file;
        displayPdf();
    } else {
        alert("Unsupported file type. Please upload an image or PDF.");
        state.file = null;
    }
};

input.addEventListener("change", () => {
    const files = input.files;
    if (files.length > 0) {
        onDrop(files[0]);
    }
});

// Reset input value on click to allow re-selecting the same file
input.addEventListener("click", (e) => {
    e.target.value = null;
});

// --- Drag and Drop functionality ---
droparea.addEventListener("drop", (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        onDrop(files[0]);
    }
});
droparea.addEventListener("dragover", (event) => {
    event.preventDefault();
});

// --- Paste functionality ---
document.onpaste = (event) => {
    event.preventDefault();
    var items = event.clipboardData?.items;
    if (!items) return;

    for (let index in items) {
        var item = items[index];
        if (item.kind === 'file') {
            const blob = item.getAsFile();
            onDrop(blob); // Process the pasted file
            return;
        }
    }
};

// --- Job Dashboard & Async OCR Logic (Simplified Display) ---
let activeJobs = {}; // Stores job_id -> job_data for easy access
const POLL_INTERVAL = 1000; // Poll server every 1 second
let pollingIntervalId = null; // To store setInterval ID for server polling
let dashboardIntervals = {}; // NEW: Store intervals for live dashboard duration updates

function startPolling() {
    if (!pollingIntervalId) {
        pollingIntervalId = setInterval(updateJobDashboard, POLL_INTERVAL);
    }
    updateJobDashboard();
}

function stopPolling() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

function updateJobDashboard() {
    const jobListEl = document.querySelector("#job-list");
    document.querySelector("#job-dashboard").classList.remove('hidden'); 

    let hasActivePollingJobs = false;
    const sortedJobIds = Object.keys(activeJobs).sort((a, b) => {
        const timeA = new Date(activeJobs[a].overall_start_time || 0).getTime();
        const timeB = new Date(activeJobs[b].overall_start_time || 0).getTime();
        return timeA - timeB;
    });

    if (sortedJobIds.length === 0) {
        if (!jobListEl.querySelector(".no-jobs-message")) {
            jobListEl.innerHTML = "<p class='no-jobs-message'>No active jobs yet.</p>";
        }
    } else {
        // Remove "No active jobs yet" if it exists
        const noJobsMsg = jobListEl.querySelector(".no-jobs-message");
        if (noJobsMsg) noJobsMsg.remove();

        sortedJobIds.forEach((jobId, index) => {
            const jobData = activeJobs[jobId];
            displayJob(jobId, jobData, index + 1);
            if (jobData.status === 'pending' || jobData.status === 'in_progress') {
                hasActivePollingJobs = true;
            }
        });
    }

    if (!hasActivePollingJobs) {
        stopPolling();
    } else {
        // Only poll for jobs that are actually active AND are async
        sortedJobIds.forEach(jobId => {
            const jobData = activeJobs[jobId];
            if ((jobData.status === 'pending' || jobData.status === 'in_progress') && !jobId.startsWith('sync-')) {
                pollJobStatus(jobId);
            }
        });
    }
}

async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`/api/ocr_status/${jobId}`);
        const jobData = await response.json();

        if (response.ok) {
            activeJobs[jobId] = { ...activeJobs[jobId], ...jobData };
            // Auto-display result of last completed job
            if (jobData.status === 'completed' || jobData.status === 'failed') {
                updateTimingInfoDisplay(jobId);
                const results = jobData.results || [];
                if (results.length > 0) {
                    resetVisualDisplay(); 
                    // Show full JSON of all results in the textarea
                    resultTextarea.value = JSON.stringify(results, null, 2);

                    // For visual display, we show the first successful result
                    const firstResult = results[0];
                    if (firstResult.image_base64 && firstResult.ocr_data) {
                        drawOCRData(firstResult.ocr_data, firstResult.image_base64);
                    } else if (firstResult.image_base64) {
                        ocrImg.src = firstResult.image_base64;
                        ocrImg.classList.remove('hidden');
                        ocrCanvas.classList.add('hidden');
                        ocrPdf.classList.add('hidden');
                    } else if (firstResult.source && (firstResult.source.endsWith(".pdf") || firstResult.filename && firstResult.filename.endsWith(".pdf"))) {
                        // Use the server-provided source URL for PDFs, ensuring correct display
                        ocrPdf.src = firstResult.source.startsWith("filepath://") ? firstResult.source.replace("filepath://", "/static/uploads/") : firstResult.source;
                        ocrPdf.classList.remove('hidden');
                        ocrImg.classList.add('hidden');
                        ocrCanvas.classList.add('hidden');
                    }
                } else if (jobData.error) {
                    resultTextarea.value = `Job Failed: ${jobData.error}`;
                }
            }
        } else {
            console.error(`Error polling job ${jobId}:`, jobData);
            activeJobs[jobId] = { ...activeJobs[jobId], status: 'failed', error: jobData.message || 'Error fetching status' };
        }
    } catch (error) {
        console.error(`Network error polling job ${jobId}:`, error);
        activeJobs[jobId] = { ...activeJobs[jobId], status: 'failed', error: 'Network error' };
    }
}

function displayJob(jobId, jobData, jobIndex) {
    const jobListEl = document.querySelector("#job-list");
    let jobEl = document.querySelector(`#job-${jobId}`);

    if (!jobEl) {
        jobEl = document.createElement('div');
        jobEl.id = `job-${jobId}`;
        jobEl.classList.add('job-entry', 'job-grid-row');
        jobListEl.appendChild(jobEl);

        jobEl.innerHTML = `
            <span class="job-col job-col-number"></span>
            <span class="job-col job-col-id"></span>
            <span class="job-col job-col-filename"></span>
            <span class="job-col job-col-progress"></span>
            <span class="job-col job-col-status"></span>
            <span class="job-col job-col-duration"></span>
        `;
        
        jobEl.onclick = () => {
            const results = jobData.results || [];
            updateTimingInfoDisplay(jobId);
            if (results.length > 0) {
                resetVisualDisplay();
                // Show full JSON of all results in the textarea
                resultTextarea.value = JSON.stringify(results, null, 2);

                const firstResult = results[0];
                if (firstResult.image_base64 && firstResult.ocr_data) {
                    drawOCRData(firstResult.ocr_data, firstResult.image_base64);
                } else if (firstResult.image_base64) {
                    ocrImg.src = firstResult.image_base64;
                    ocrImg.classList.remove('hidden');
                    ocrCanvas.classList.add('hidden');
                    ocrPdf.classList.add('hidden');
                } else if (firstResult.source && (firstResult.source.endsWith(".pdf") || firstResult.filename && firstResult.filename.endsWith(".pdf"))) {
                    // Use the server-provided source URL for PDFs
                    ocrPdf.src = firstResult.source.startsWith("filepath://") ? firstResult.source.replace("filepath://", "/static/uploads/") : firstResult.source;
                    ocrPdf.classList.remove('hidden');
                    ocrImg.classList.add('hidden');
                    ocrCanvas.classList.add('hidden');
                }
            } else if (jobData.status === 'pending' || jobData.status === 'in_progress') {
                resultTextarea.value = `Job is ${jobData.status}...`;
            } else {
                resultTextarea.value = "No results available for this job yet.";
            }
        };
    }

    jobEl.querySelector('.job-col-number').textContent = `${jobIndex}.`;
    jobEl.querySelector('.job-col-id').textContent = jobId.substring(0, 8);
    
    const initialFilesPayload = jobData.files || [];
    const totalFiles = initialFilesPayload.length > 0 ? initialFilesPayload.length : (jobData.results ? jobData.results.length : 0);
    const completedFiles = jobData.results ? jobData.results.filter(res => !res.error).length : 0;
    jobEl.querySelector('.job-col-progress').textContent = `${completedFiles}/${totalFiles}`;
    
    let mainFilename = "N/A";
    if (jobData.results && jobData.results.length > 0) {
        const firstResult = jobData.results[0];
        mainFilename = firstResult.filename || firstResult.source || "N/A";
    } else if (initialFilesPayload.length > 0) {
        const firstFile = initialFilesPayload[0];
        mainFilename = firstFile.filename || firstFile.url || "N/A";
    }
    if (mainFilename.length > 20) mainFilename = mainFilename.substring(0, 17) + "...";
    jobEl.querySelector('.job-col-filename').textContent = mainFilename;

    const statusSpan = jobEl.querySelector('.job-col-status');
    const durationSpan = jobEl.querySelector('.job-col-duration');

    if (jobData.status === 'in_progress') {
        if (!statusSpan.querySelector(".flashing-dot")) {
            statusSpan.innerHTML = `<span class="flashing-dot"></span>${jobData.status}`;
        }
    } else {
        statusSpan.textContent = jobData.status;
    }
    
    statusSpan.classList.remove('status-pending', 'status-in_progress', 'status-completed', 'status-failed');
    statusSpan.classList.add(`job-status`, `status-${jobData.status}`);

    if (jobData.status === 'completed' || jobData.status === 'failed') {
        durationSpan.textContent = jobData.overall_duration || "N/A";
        if (dashboardIntervals[jobId]) {
            clearInterval(dashboardIntervals[jobId]);
            delete dashboardIntervals[jobId];
        }
    } else {
        // Live update dashboard duration
        if (!dashboardIntervals[jobId] && jobData.overall_start_time) {
            dashboardIntervals[jobId] = setInterval(() => {
                const job = activeJobs[jobId];
                if (!job || job.status === 'completed' || job.status === 'failed') {
                    if (dashboardIntervals[jobId]) {
                        clearInterval(dashboardIntervals[jobId]);
                        delete dashboardIntervals[jobId];
                    }
                    return;
                }
                const startTime = new Date(job.overall_start_time).getTime();
                if (isNaN(startTime) || startTime <= 0) {
                    durationSpan.textContent = '0.00s';
                    return;
                }
                const now = Date.now();
                const elapsed = Math.max(0, (now - startTime) / 1000).toFixed(2);
                durationSpan.textContent = elapsed + 's';
            }, 100);
        }
    }
}

// --- Job Timing Logic ---
let timingIntervalId = null;
let currentTimingJobId = null;

function updateTimingInfoDisplay(jobId) {
    const jobData = activeJobs[jobId];
    if (!jobData) return;

    currentTimingJobId = jobId;
    const timingInfoEl = document.querySelector("#timing-info");
    const startTimeEl = document.querySelector("#start-time");
    const endTimeEl = document.querySelector("#end-time");
    const durationEl = document.querySelector("#duration");

    timingInfoEl.classList.remove("hidden");
    startTimeEl.textContent = jobData.overall_start_time ? new Date(jobData.overall_start_time).toLocaleTimeString() : 'N/A';
    
    if (jobData.status === 'completed' || jobData.status === 'failed') {
        endTimeEl.textContent = jobData.overall_end_time ? new Date(jobData.overall_end_time).toLocaleTimeString() : 'N/A';
        durationEl.textContent = jobData.overall_duration || 'N/A';
        // Stop any active interval if this is the job we're tracking
        if (timingIntervalId) {
            clearInterval(timingIntervalId);
            timingIntervalId = null;
        }
    } else {
        endTimeEl.textContent = 'Running...';
        // Clear any previous interval before starting a new one
        if (timingIntervalId) {
            clearInterval(timingIntervalId);
            timingIntervalId = null;
        }
        
        // Start live duration update
        timingIntervalId = setInterval(() => {
            if (currentTimingJobId && activeJobs[currentTimingJobId]) {
                const job = activeJobs[currentTimingJobId];
                if (job.status === 'completed' || job.status === 'failed') {
                    durationEl.textContent = job.overall_duration || 'N/A';
                    endTimeEl.textContent = job.overall_end_time ? new Date(job.overall_end_time).toLocaleTimeString() : 'N/A';
                    clearInterval(timingIntervalId);
                    timingIntervalId = null;
                    return;
                }
                const startTime = new Date(job.overall_start_time).getTime();
                if (isNaN(startTime) || startTime <= 0) {
                    durationEl.textContent = '0.00s';
                    return;
                }
                const now = Date.now();
                const elapsed = Math.max(0, (now - startTime) / 1000).toFixed(2);
                durationEl.textContent = elapsed + 's';
            }
        }, 100);
    }
}


function doOCR(){
    const resultEl = document.querySelector("#resulttext");
    resultEl.value = "Scanning..."; // Clear previous results and show scanning message
    
    // Provide visual feedback instead of clearing everything
    document.querySelector('main').classList.add('scanning');

    var data = new FormData();
    const language = document.getElementById('source_lang').value;
    if (!state.file) {
        alert("Please select a file first.");
        document.querySelector('main').classList.remove('scanning');
        return;
    }
    data.append('file', state.file);
    data.append('language', language);
    
    const jobId = 'sync-' + Date.now();
    data.append('job_id', jobId); // Send job_id to server
    
    activeJobs[jobId] = {
        job_id: jobId,
        status: 'in_progress',
        results: [],
        overall_start_time: new Date().toISOString(),
        overall_end_time: null,
        overall_duration: null,
        error: null,
        files: [{ filename: state.file.name, language: language }]
    };
    displayJob(jobId, activeJobs[jobId]);
    updateTimingInfoDisplay(jobId);
    startPolling(); // Ensure polling is active for job updates

    fetch('/api/ocr', {
      method: 'POST',
      body: data
    })
    .then(response => {
        document.querySelector('main').classList.remove('scanning');
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || 'Server error'); });
        }
        return response.json();
    })
    .then(result => {
        activeJobs[jobId] = {
            ...activeJobs[jobId],
            status: result.error ? 'failed' : 'completed',
            results: [{ ...result, filename: state.file.name }],
            overall_start_time: result.start_time || activeJobs[jobId].overall_start_time,
            overall_end_time: result.end_time || new Date().toISOString(),
            overall_duration: result.duration,
            error: result.error
        };
        displayJob(jobId, activeJobs[jobId]); // Update job entry in dashboard
        updateTimingInfoDisplay(jobId); // Update final timing info display

        resultEl.value = JSON.stringify(result, null, 2); // Show JSON result

        if (result.image_base64 && result.ocr_data) {
            drawOCRData(result.ocr_data, result.image_base64);
        } else if (result.image_base64) {
            ocrImg.src = result.image_base64;
            ocrImg.classList.remove('hidden');
            ocrCanvas.classList.add('hidden');
            ocrPdf.classList.add('hidden');
        } else if (state.file.type.indexOf("application/pdf") >= 0) {
            // For local PDF, use the blob URL from state.file
            ocrPdf.src = URL.createObjectURL(state.file);
            ocrPdf.classList.remove('hidden');
            ocrImg.classList.add('hidden');
            ocrCanvas.classList.add('hidden');
        }
    })
    .catch(error => {
        document.querySelector('main').classList.remove('scanning');
        console.error("Error during OCR:", error);
        activeJobs[jobId] = {
            ...activeJobs[jobId],
            status: 'failed',
            overall_end_time: new Date().toISOString(),
            overall_duration: 'N/A',
            error: error.message || error
        };
        displayJob(jobId, activeJobs[jobId]);

        resultEl.value = `Error: ${error.message || error}`;
    });
}

async function submitAsyncOCR(){
    const resultEl = document.querySelector("#resulttext");
    resultEl.value = "Submitting async job...";
    
    // Provide visual feedback instead of clearing everything
    document.querySelector('main').classList.add('scanning');

    const uploadImageInput = document.querySelector("#uploadimage");
    const selectedFiles = uploadImageInput.files;
    
    if (selectedFiles.length === 0) {
        alert("Please select at least one file for asynchronous processing.");
        document.querySelector('main').classList.remove('scanning');
        return;
    }

    const filesPayload = [];
    for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        
        const base64String = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = error => reject(error);
            reader.readAsDataURL(file);
        });

        filesPayload.push({
            filename: file.name,
            base64: base64String,
            language: document.getElementById('source_lang').value
        });
    }

    try {
        const response = await fetch('/api/async_ocr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: filesPayload })
        });

        const jsonResponse = await response.json();
        document.querySelector('main').classList.remove('scanning');

        if (response.ok) {
            const jobId = jsonResponse.job_id;
            activeJobs[jobId] = {
                job_id: jobId,
                status: jsonResponse.status,
                results: [],
                overall_start_time: new Date().toISOString(),
                overall_end_time: null,
                overall_duration: null,
                error: null,
                files: filesPayload
            };
            displayJob(jobId, activeJobs[jobId]);
            updateTimingInfoDisplay(jobId);
            startPolling();
            resultEl.value = jsonResponse.message;
        } else {
            resultEl.value = `Error submitting async job: ${jsonResponse.error || response.statusText}`;
        }
    } catch (error) {
        document.querySelector('main').classList.remove('scanning');
        console.error("Error submitting async job:", error);
        resultEl.value = `Network Error: ${error.message || error}`;
    }
}
