const droparea = document.querySelector(".drop")
const input = document.querySelector("#uploadimage")

let state = {
    isDragging: false,
    wrongFile: false,
    file: null
}

input.addEventListener("change", () => {
    const files = input.files
    if (files.length > 0) {
        onDrop(files[0]);
    }
})

const dragOver = () => {
    state.isDragging = true;
};
const dragLeave = () => {
    state.isDragging = false;
};

const displayImage = () => {
  document.querySelector("#ocr-img").src=URL.createObjectURL(state.file);
  document.querySelector("#ocr-img").classList.remove('hidden');
  document.querySelector("#ocr-pdf").classList.add('hidden');
}

const displayPdf = () => {
    document.querySelector("#ocr-img").classList.add('hidden');
    document.querySelector("#ocr-pdf").src=URL.createObjectURL(state.file);
  document.querySelector("#ocr-pdf").classList.remove('hidden');
}

const onDrop = (file) => {
    // allows image only
    if (file.type.indexOf("image/") >= 0) {
        state.file=file
        displayImage()
    } else if (file.type.indexOf("application/pdf") >= 0) {
        state.file=file
        displayPdf()
    } else {
        alert("Unsupported file type. Please upload an image or PDF.");
        state.file = null;
        document.querySelector("#ocr-img").classList.add('hidden');
        document.querySelector("#ocr-pdf").classList.add('hidden');
    }
}

droparea.addEventListener("drop", (e) => {
    e.preventDefault()
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        onDrop(files[0])
    }
})

document.querySelector("#ocr-img").addEventListener("drop", (e) => {
    e.preventDefault()
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        onDrop(files[0])
    }
})

droparea.addEventListener("dragover", (event) => {
    // prevent default to allow drop
    event.preventDefault();
  });

document.onpaste = (event) => {
    event.preventDefault();
    var items = event.clipboardData?.items;
    if (!items) return;

    for (let index in items) {
        var item = items[index];
        if (item.kind === 'file') {
            const blob = item.getAsFile();
            const reader = new FileReader();
            reader.onload = (pasteEvent) => {
                state.imageSource = pasteEvent.target?.result;
            };
            reader.readAsDataURL(blob);
            onDrop(blob);
            return; // Process only the first pasted file
        }
    }
};

// --- Job Dashboard & Async OCR Logic ---
let activeJobs = {}; // Stores job_id -> job_data for easy access
const POLL_INTERVAL = 1000; // Poll server every 1 second
const DISPLAY_UPDATE_INTERVAL = 50; // Update client-side duration every 50ms
let pollingIntervalId = null; // To store setInterval ID for server polling
let displayUpdateIntervals = {}; // To store setInterval IDs for client-side duration updates per job

function startPolling() {
    if (!pollingIntervalId) { // Only start if not already running
        pollingIntervalId = setInterval(updateJobDashboard, POLL_INTERVAL);
    }
    updateJobDashboard(); // Call immediately to avoid initial delay
}

function stopPolling() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
    // Also clear all individual display update intervals
    for (const jobId in displayUpdateIntervals) {
        clearInterval(displayUpdateIntervals[jobId]);
        delete displayUpdateIntervals[jobId];
    }
}

function updateJobDashboard() {
    const jobListEl = document.querySelector("#job-list");
    jobListEl.classList.remove('hidden'); // Ensure job list is visible
    document.querySelector("#job-dashboard").classList.remove('hidden'); // Ensure dashboard section is visible

    let hasActivePollingJobs = false;
    // Get sorted job IDs to maintain a consistent order (e.g., by submission time)
    const sortedJobIds = Object.keys(activeJobs).sort((a, b) => {
        const timeA = new Date(activeJobs[a].overall_start_time || 0).getTime();
        const timeB = new Date(activeJobs[b].overall_start_time || 0).getTime();
        return timeA - timeB;
    });

    // Clear existing jobs in the list to re-render in sorted order
    jobListEl.innerHTML = ""; 

    if (sortedJobIds.length === 0) {
        jobListEl.innerHTML = "<p class='no-jobs-message'>No active jobs yet.</p>"; // Add class to the message
    } else {
        sortedJobIds.forEach((jobId, index) => {
            const jobData = activeJobs[jobId];
            displayJob(jobId, jobData, index + 1); // Pass jobIndex for numbering
            if (jobData.status === 'pending' || jobData.status === 'in_progress') {
                hasActivePollingJobs = true;
                pollJobStatus(jobId); // Poll server for status
            } else {
                stopClientSideDurationUpdate(jobId); // Ensure client-side duration updates are stopped
            }
        });
    }

    // If no active jobs requiring server polling, stop server polling
    if (!hasActivePollingJobs) {
        stopPolling();
    }

    // Check for a recently completed job and update resultEl
    const lastCompletedOrFailedJob = sortedJobIds
        .map(jobId => activeJobs[jobId])
        .filter(job => (job.status === 'completed' || job.status === 'failed') && job.overall_end_time) // Ensure it has end time
        .sort((a, b) => new Date(b.overall_end_time).getTime() - new Date(a.overall_end_time).getTime())[0];

    if (lastCompletedOrFailedJob) {
        const resultEl = document.querySelector("#resulttext");
        const currentResultElValue = resultEl.value;
        let lastJobIdInResultEl = null;

        // Attempt to parse existing content only if it's not empty, to avoid errors with "Scanning..." etc.
        if (currentResultElValue && currentResultElValue.startsWith('{')) { // Simple check to see if it might be JSON
            try {
                const parsedResult = JSON.parse(currentResultElValue);
                lastJobIdInResultEl = parsedResult.job_id || null;
            } catch (e) {
                // Not valid JSON, or not a job result
                lastJobIdInResultEl = null;
            }
        }

        // Always update if no job is currently displayed or a different job has completed
        // This ensures the most recent completion is always shown.
        if (!lastJobIdInResultEl || lastJobIdInResultEl !== lastCompletedOrFailedJob.job_id) {
             resultEl.value = JSON.stringify(lastCompletedOrFailedJob, null, 2);
             updateTimingInfoDisplay(lastCompletedOrFailedJob.overall_start_time, lastCompletedOrFailedJob.overall_end_time, lastCompletedOrFailedJob.overall_duration);
        }
    }
}


async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`/api/ocr_status/${jobId}`);
        const jobData = await response.json();

        if (response.ok) {
            // Merge new data into activeJobs, but keep initial files payload
            activeJobs[jobId] = { ...activeJobs[jobId], ...jobData };
            // displayJob is called inside updateJobDashboard loop, so no need to call it directly here
        } else {
            console.error(`Error polling job ${jobId}:`, jobData);
            activeJobs[jobId] = { ...activeJobs[jobId], status: 'failed', error: jobData.message || 'Error fetching status' };
        }
    } catch (error) {
        console.error(`Network error polling job ${jobId}:`, error);
        activeJobs[jobId] = { ...activeJobs[jobId], status: 'failed', error: 'Network error' };
    }
}

function startClientSideDurationUpdate(jobId, jobData) {
    if (!displayUpdateIntervals[jobId] && (jobData.status === 'pending' || jobData.status === 'in_progress') && jobData.overall_start_time) {
        const startTime = new Date(jobData.overall_start_time);
        displayUpdateIntervals[jobId] = setInterval(() => {
            const now = new Date();
            const elapsedMs = now.getTime() - startTime.getTime();
            const formattedDuration = `${(elapsedMs / 1000).toFixed(2)}s`;
            // Update the duration span directly if jobEl is already in DOM
            const jobEl = document.querySelector(`#job-${jobId}`);
            if (jobEl) {
                const durationSpan = jobEl.querySelector('.job-col-duration');
                if (durationSpan) {
                    durationSpan.textContent = formattedDuration;
                }
            }
        }, DISPLAY_UPDATE_INTERVAL);
    }
}

function stopClientSideDurationUpdate(jobId) {
    if (displayUpdateIntervals[jobId]) {
        clearInterval(displayUpdateIntervals[jobId]);
        delete displayUpdateIntervals[jobId];
    }
}

function displayJob(jobId, jobData, jobIndex) { // NEW: Added jobIndex
    const jobListEl = document.querySelector("#job-list");
    let jobEl = document.querySelector(`#job-${jobId}`);

    // If jobEl doesn't exist, create it as a div element and append spans
    if (!jobEl) {
        jobEl = document.createElement('div'); // Changed to <div>
        jobEl.id = `job-${jobId}`;
        jobEl.classList.add('job-entry', 'job-grid-row'); // Add job-grid-row class
        jobListEl.appendChild(jobEl);

        // Append individual span elements once
        jobEl.innerHTML = `
            <span class="job-col job-col-number"></span>
            <span class="job-col job-col-id"></span>
            <span class="job-col job-col-filename"></span>
            <span class="job-col job-col-progress"></span>
            <span class="job-col job-col-status"></span>
            <span class="job-col job-col-duration"></span>
        `;
        
        // Make the newly created jobEl clickable to show full results
        jobEl.onclick = () => {
            const resultEl = document.querySelector("#resulttext");
            resultEl.value = JSON.stringify(jobData, null, 2);
            updateTimingInfoDisplay(jobData.overall_start_time, jobData.overall_end_time, jobData.overall_duration);
        };
    }

    // --- Update individual span contents ---
    jobEl.querySelector('.job-col-number').textContent = `${jobIndex}.`;
    jobEl.querySelector('.job-col-id').textContent = jobId.substring(0, 8);

    // Determine total files and completed files
    const initialFilesPayload = jobData.files || [];
    const totalFiles = initialFilesPayload.length > 0 ? initialFilesPayload.length : (jobData.results ? jobData.results.length : 0);
    const completedFiles = jobData.results ? jobData.results.filter(res => !res.error).length : 0;
    jobEl.querySelector('.job-col-progress').textContent = `${completedFiles}/${totalFiles}`;

    // Determine the main filename to display
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

    // Update status and duration
    const statusSpan = jobEl.querySelector('.job-col-status');
    statusSpan.textContent = jobData.status;
    // Remove all status classes first, then add the correct one
    statusSpan.classList.remove('status-pending', 'status-in_progress', 'status-completed', 'status-failed', 'flashing-green', 'flashing-red', 'flashing-blue'); // Also remove flashing-green
    statusSpan.classList.add(`job-status`, `status-${jobData.status}`); // Add base status class

    if (jobData.status === 'pending' || jobData.status === 'in_progress') {
        // startClientSideDurationUpdate handles updating the duration span
        startClientSideDurationUpdate(jobId, jobData);
    } else {
        stopClientSideDurationUpdate(jobId);
        jobEl.querySelector('.job-col-duration').textContent = jobData.overall_duration || "N/A";
    }

    // Update timing info for the "last completed job" if this one just completed
    if (jobData.status === 'completed' || jobData.status === 'failed') {
        updateTimingInfoDisplay(jobData.overall_start_time, jobData.overall_end_time, jobData.overall_duration);
    }
    // Remove "No active jobs yet." paragraph if there are active jobs
    const noJobsP = jobListEl.querySelector("p.no-jobs-message");
    if (noJobsP && noJobsP.parentNode === jobListEl) { // Ensure it's the direct child of jobListEl
        noJobsP.remove();
    }
}

// Helper function to update the top timing info display
function updateTimingInfoDisplay(startTimeISO, endTimeISO, durationValue) {
    const timingInfoEl = document.querySelector("#timing-info");
    const startTimeEl = document.querySelector("#start-time");
    const endTimeEl = document.querySelector("#end-time");
    const durationEl = document.querySelector("#duration");

    timingInfoEl.classList.remove("hidden");
    timingInfoEl.style.display = 'block'; // Explicitly set display to block

    startTimeEl.textContent = startTimeISO ? new Date(startTimeISO).toLocaleTimeString() : 'N/A';
    endTimeEl.textContent = endTimeISO ? new Date(endTimeISO).toLocaleTimeString() : 'N/A';
    durationEl.textContent = durationValue || 'N/A';
}


// Function for submitting single file (Sync) - original doOCR
function doOCR(){
    const resultEl = document.querySelector("#resulttext")
    var data = new FormData()
    const language = document.getElementById('source_lang').value;
    if (!state.file) {
        resultEl.value = "Please select a file first.";
        return;
    }
    data.append('file', state.file)
    data.append('language',language)
    resultEl.value  = "Scanning..."

    // --- NEW: Handle Sync Job for Dashboard ---
    const jobId = 'sync-' + Date.now(); // Generate a unique ID for sync job
    activeJobs[jobId] = {
        job_id: jobId,
        status: 'in_progress', // Starts in progress
        results: [],
        overall_start_time: new Date().toISOString(),
        overall_end_time: null,
        overall_duration: null,
        error: null,
        files: [{ filename: state.file.name, language: language }] // Initial payload for display
    };
    displayJob(jobId, activeJobs[jobId]);
    // --- END NEW ---

    // Reset timing info display (will be updated by the result now)
    updateTimingInfoDisplay(null, null, null);


    fetch('/api/ocr', {
      method: 'POST',
      body: data
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || 'Server error'); });
        }
        return response.json();
    })
    .then(result => {
        // Update job status in activeJobs and display
        activeJobs[jobId] = {
            ...activeJobs[jobId],
            status: result.error ? 'failed' : 'completed',
            results: [{ ...result, filename: state.file.name }], // Add result to results array
            overall_end_time: result.end_time || new Date().toISOString(), // Use server time if available
            overall_duration: result.duration, // Use server-provided duration
            error: result.error
        };
        displayJob(jobId, activeJobs[jobId]); // Update job entry in dashboard

        // Paste full JSON results in results pane
        resultEl.value = JSON.stringify(result, null, 2);
        
        // Update top timing info for this completed sync job
        updateTimingInfoDisplay(result.start_time, result.end_time, result.duration);
    })
    .catch(error => {
        console.error("Error during OCR:", error);
        // Update job status in activeJobs and display for failure
        activeJobs[jobId] = {
            ...activeJobs[jobId],
            status: 'failed',
            overall_end_time: new Date().toISOString(),
            overall_duration: 'N/A', // Cannot determine without server response
            error: error.message || error
        };
        displayJob(jobId, activeJobs[jobId]); // Update job entry in dashboard

        resultEl.value = `Error: ${error.message || error}`;
        updateTimingInfoDisplay(activeJobs[jobId].overall_start_time, activeJobs[jobId].overall_end_time, activeJobs[jobId].overall_duration);
    })
}

// NEW: Function for submitting multiple files (Async)
async function submitAsyncOCR(){
    const resultEl = document.querySelector("#resulttext")
    const uploadImageInput = document.querySelector("#uploadimage");
    
    // For simplicity, let's assume we collect multiple files from the input field
    // In a real app, this would be a more sophisticated UI for multiple file selection/drag-drop
    const selectedFiles = uploadImageInput.files;
    
    if (selectedFiles.length === 0) {
        alert("Please select at least one file for asynchronous processing.");
        return;
    }

    const filesPayload = [];
    for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        
        // Convert file to Base64
        const base64String = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(',')[1]); // Get base64 part
            reader.onerror = error => reject(error);
            reader.readAsDataURL(file);
        });

        filesPayload.push({
            filename: file.name,
            base64: base64String,
            language: document.getElementById('source_lang').value // Use selected language
        });
    }

    try {
        resultEl.value  = "Submitting async job..."
        const response = await fetch('/api/async_ocr', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ files: filesPayload })
        });

        const jsonResponse = await response.json();

        if (response.ok) {
            const jobId = jsonResponse.job_id;
            activeJobs[jobId] = {
                job_id: jobId,
                status: jsonResponse.status,
                results: [], // Will be populated by polling
                overall_start_time: new Date().toISOString(),
                overall_end_time: null,
                overall_duration: null,
                error: null,
                files: filesPayload // NEW: Store initial files payload
            };
            displayJob(jobId, activeJobs[jobId]);
            startPolling(); // Ensure polling is active
            resultEl.value = jsonResponse.message;
        } else {
            resultEl.value = `Error submitting async job: ${jsonResponse.error || response.statusText}`;
        }
    } catch (error) {
        console.error("Error submitting async job:", error);
        resultEl.value = `Network Error: ${error.message || error}`;
    }
}

// Initialize polling when page loads if there are any jobs (e.g. from previous session, though not persistent now)
// Or simply start when first async job is submitted.

// --- Styling for job dashboard (will go into main.css) ---
/*
.job-entry {
    border: 1px solid var(--border-color);
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 5px;
    background-color: var(--background-color);
}
.job-status {
    font-weight: bold;
}
.job-status.status-pending { color: orange; }
.job-status.status-in_progress { color: lightblue; }
.job-status.status-completed { color: limegreen; }
.job-status.status-failed { color: red; }
.job-error {
    color: red;
    font-weight: bold;
}
.job-results {
    list-style: none;
    padding-left: 0;
}
.job-results li {
    margin-bottom: 5px;
    border-bottom: 1px dashed var(--border-color);
    padding-bottom: 5px;
}
*/
