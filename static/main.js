const droparea = document.querySelector(".controls-area");
const input = document.querySelector("#uploadimage");
const ocrImg = document.querySelector("#ocr-img");
const ocrPdf = document.querySelector("#ocr-pdf");
const ocrCanvas = document.querySelector("#ocr-canvas");
const fileDisplayContainer = document.querySelector("#file-display-container");
const resultTextarea = document.querySelector("#resulttext");
const fileResizer = document.querySelector("#file-display-resizer");
const pdfControls = document.querySelector("#pdf-controls");
const pageNumSpan = document.querySelector("#page-num");
const pageCountSpan = document.querySelector("#page-count");

// --- Custom Resize Logic ---
let isResizing = false;

fileResizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.body.style.cursor = 'ns-resize';
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
    if (newHeight > 200) {
        fileDisplayContainer.style.height = newHeight + 'px';
        fileDisplayContainer.style.minHeight = newHeight + 'px';
    }
}

let state = {
    isDragging: false,
    wrongFile: false,
    file: null,
    currentOcrResults: null // Array of page results
};

let pdfState = {
    pdfDoc: null,
    pageNum: 1,
    pageRendering: false,
    pageNumPending: null,
    currentUrl: null
};

// --- Core Display Functions ---
function resetVisualDisplay(isResultFlow = false) {
    ocrImg.classList.add('hidden');
    ocrPdf.classList.add('hidden');
    ocrCanvas.classList.add('hidden');
    pdfControls.classList.add('hidden');
    if (!isResultFlow) {
        resultTextarea.value = "";
        state.currentOcrResults = null;
    }
}

function displayImage(src) {
    resetVisualDisplay(src ? true : false); 
    ocrImg.src = src || URL.createObjectURL(state.file);
    ocrImg.classList.remove('hidden');
    ocrCanvas.classList.add('hidden');
}

async function displayPdf(src) {
    resetVisualDisplay(src ? true : false);
    const url = src || URL.createObjectURL(state.file);
    
    try {
        if (pdfState.currentUrl !== url) {
            pdfState.pdfDoc = await pdfjsLib.getDocument(url).promise;
            pdfState.currentUrl = url;
        }
        pdfState.pageNum = 1;
        pageCountSpan.textContent = pdfState.pdfDoc.numPages;
        pdfControls.classList.remove('hidden');
        await renderPdfPage(pdfState.pageNum);
    } catch (error) {
        console.error("Error loading PDF with PDF.js:", error);
        ocrPdf.src = url;
        ocrPdf.classList.remove('hidden');
    }
}

async function renderPdfPage(num) {
    if (!pdfState.pdfDoc) return;
    pdfState.pageRendering = true;
    pdfState.pageNum = num;
    
    const page = await pdfState.pdfDoc.getPage(num);
    const viewport = page.getViewport({ scale: 1.5 });
    ocrCanvas.height = viewport.height;
    ocrCanvas.width = viewport.width;

    const renderContext = {
        canvasContext: ocrCanvas.getContext('2d'),
        viewport: viewport
    };
    
    await page.render(renderContext).promise;
    pdfState.pageRendering = false;
    ocrCanvas.classList.remove('hidden');
    pageNumSpan.textContent = num;

    if (pdfState.pageNumPending !== null) {
        renderPdfPage(pdfState.pageNumPending);
        pdfState.pageNumPending = null;
    }

    // Draw bounding boxes for this page
    if (state.currentOcrResults && Array.isArray(state.currentOcrResults)) {
        console.log(`Checking for OCR data for page ${num} in`, state.currentOcrResults);
        const pageOcr = state.currentOcrResults.find(res => res.page_num === num);
        if (pageOcr) {
            console.log(`Found data for page ${num}, drawing boxes.`);
            drawBoundingBoxes(pageOcr.ocr_data, pageOcr.image_width, pageOcr.image_height);
        } else {
            console.warn(`No OCR data found for page ${num}`);
        }
    }
}

function queueRenderPage(num) {
    if (pdfState.pageRendering) {
        pdfState.pageNumPending = num;
    } else {
        renderPdfPage(num);
    }
}

function prevPage() {
    if (pdfState.pageNum <= 1) return;
    queueRenderPage(pdfState.pageNum - 1);
}
window.prevPage = prevPage;

function nextPage() {
    if (!pdfState.pdfDoc || pdfState.pageNum >= pdfState.pdfDoc.numPages) return;
    queueRenderPage(pdfState.pageNum + 1);
}
window.nextPage = nextPage;

function drawBoundingBoxes(pageData, originalWidth, originalHeight) {
    const ctx = ocrCanvas.getContext('2d');
    console.log(`Drawing ${pageData.length} boxes. Canvas: ${ocrCanvas.width}x${ocrCanvas.height}, Original: ${originalWidth}x${originalHeight}`);
    
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 2;
    ctx.fillStyle = 'rgba(255, 0, 0, 0.1)';

    const scaleX = ocrCanvas.width / originalWidth;
    const scaleY = ocrCanvas.height / originalHeight;
    console.log(`Scales: X=${scaleX}, Y=${scaleY}`);
    
    pageData.forEach(item => {
        if (item.level === 5 && item.text && item.text.trim() !== '') {
            const left = item.left * scaleX;
            const top = item.top * scaleY;
            const width = item.width * scaleX;
            const height = item.height * scaleY;
            ctx.strokeRect(left, top, width, height);
            ctx.fillRect(left, top, width, height);
        }
    });
}

async function drawOCRData(fileResult) {
    console.log("drawOCRData called with:", fileResult);
    if (!fileResult) return;
    
    if (fileResult.image_base64) {
        console.log("Detected Image result");
        // Single image result - ocr_data is the array of page results
        state.currentOcrResults = fileResult.ocr_data; 
        const pageInfo = fileResult.ocr_data[0];
        const img = new Image();
        img.onload = () => {
            ocrCanvas.width = img.width;
            ocrCanvas.height = img.height;
            const ctx = ocrCanvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            drawBoundingBoxes(pageInfo.ocr_data, pageInfo.image_width, pageInfo.image_height);
            
            ocrCanvas.classList.remove('hidden');
            ocrImg.classList.add('hidden');
            ocrPdf.classList.add('hidden');
            pdfControls.classList.add('hidden');
        };
        img.src = fileResult.image_base64;
    } else if (Array.isArray(fileResult)) {
        console.log("Detected PDF result (array)");
        // PDF result (array of page results) - we take the first file's page results
        // fileResult is activeJobs[jobId].results, which is [ {filename:..., ocr_data: [page1, page2...]} ]
        state.currentOcrResults = fileResult[0].ocr_data;
        const firstFile = fileResult[0];
        const url = firstFile.source.startsWith("filepath://") ? firstFile.source.replace("filepath://", "/static/uploads/") : firstFile.source;
        await displayPdf(url);
    } else {
        console.warn("Unknown fileResult structure:", fileResult);
    }
}

const onDrop = (file) => {
    resetVisualDisplay();
    state.file = file;
    if (file.type.indexOf("image/") >= 0) {
        displayImage();
    } else if (file.type.indexOf("application/pdf") >= 0) {
        displayPdf();
    } else {
        alert("Unsupported file type. Please upload an image or PDF.");
        state.file = null;
    }
};

input.addEventListener("change", () => {
    if (input.files.length > 0) onDrop(input.files[0]);
});

input.addEventListener("click", (e) => { e.target.value = null; });

droparea.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length > 0) onDrop(e.dataTransfer.files[0]);
});
droparea.addEventListener("dragover", (e) => e.preventDefault());

document.onpaste = (event) => {
    const items = event.clipboardData?.items;
    if (!items) return;
    for (let index in items) {
        if (items[index].kind === 'file') {
            onDrop(items[index].getAsFile());
            return;
        }
    }
};

// --- Job Dashboard & Async OCR Logic ---
let activeJobs = {};
const POLL_INTERVAL = 1000;
let pollingIntervalId = null;
let dashboardIntervals = {};

function startPolling() {
    if (!pollingIntervalId) pollingIntervalId = setInterval(updateJobDashboard, POLL_INTERVAL);
    updateJobDashboard();
}

function stopPolling() {
    if (pollingIntervalId) { clearInterval(pollingIntervalId); pollingIntervalId = null; }
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
        if (!jobListEl.querySelector(".no-jobs-message")) jobListEl.innerHTML = "<p class='no-jobs-message'>No active jobs yet.</p>";
    } else {
        const noJobsMsg = jobListEl.querySelector(".no-jobs-message");
        if (noJobsMsg) noJobsMsg.remove();
        sortedJobIds.forEach((jobId, index) => {
            displayJob(jobId, activeJobs[jobId], index + 1);
            if (activeJobs[jobId].status === 'pending' || activeJobs[jobId].status === 'in_progress') hasActivePollingJobs = true;
        });
    }

    if (!hasActivePollingJobs) stopPolling();
    else {
        sortedJobIds.forEach(jobId => {
            if ((activeJobs[jobId].status === 'pending' || activeJobs[jobId].status === 'in_progress') && !jobId.startsWith('sync-')) pollJobStatus(jobId);
        });
    }
}

async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`/api/ocr_status/${jobId}`);
        const jobData = await response.json();
        if (response.ok) {
            activeJobs[jobId] = { ...activeJobs[jobId], ...jobData };
            if (jobData.status === 'completed' || jobData.status === 'failed') {
                updateTimingInfoDisplay(jobId);
                if (jobData.results?.length > 0) {
                    // Show full JSON of all results in the textarea
                    resultTextarea.value = JSON.stringify(jobData.results, null, 2);
                    
                    const firstResult = jobData.results[0];
                    if (firstResult.image_base64) {
                        drawOCRData(firstResult);
                    } else {
                        drawOCRData(jobData.results);
                    }
                }
            }
        }
    } catch (error) { console.error("Polling error:", error); }
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
            updateTimingInfoDisplay(jobId);
            if (jobData.results?.length > 0) {
                resultTextarea.value = JSON.stringify(jobData.results, null, 2);
                
                const firstResult = jobData.results[0];
                if (firstResult.image_base64) {
                    drawOCRData(firstResult);
                } else {
                    drawOCRData(jobData.results);
                }
            }
        };
    }

    jobEl.querySelector('.job-col-number').textContent = `${jobIndex}.`;
    jobEl.querySelector('.job-col-id').textContent = jobId.substring(0, 8);
    const totalFiles = (jobData.files || []).length || (jobData.results || []).length || 0;
    const completedFiles = (jobData.results || []).filter(res => !res.error).length;
    jobEl.querySelector('.job-col-progress').textContent = `${completedFiles}/${totalFiles}`;
    
    let mainFilename = "N/A";
    if (jobData.results?.length > 0) mainFilename = jobData.results[0].filename || jobData.results[0].source || "N/A";
    else if (jobData.files?.length > 0) mainFilename = jobData.files[0].filename || jobData.files[0].url || "N/A";
    jobEl.querySelector('.job-col-filename').textContent = mainFilename.length > 20 ? mainFilename.substring(0, 17) + "..." : mainFilename;

    const statusSpan = jobEl.querySelector('.job-col-status');
    const durationSpan = jobEl.querySelector('.job-col-duration');

    if (jobData.status === 'in_progress' && !statusSpan.querySelector(".flashing-dot")) statusSpan.innerHTML = `<span class="flashing-dot"></span>${jobData.status}`;
    else if (jobData.status !== 'in_progress') statusSpan.textContent = jobData.status;
    
    statusSpan.classList.remove('status-pending', 'status-in_progress', 'status-completed', 'status-failed');
    statusSpan.classList.add(`job-status`, `status-${jobData.status}`);

    if (jobData.status === 'completed' || jobData.status === 'failed') {
        durationSpan.textContent = jobData.overall_duration || "N/A";
        if (dashboardIntervals[jobId]) { clearInterval(dashboardIntervals[jobId]); delete dashboardIntervals[jobId]; }
    } else if (!dashboardIntervals[jobId] && jobData.overall_start_time) {
        dashboardIntervals[jobId] = setInterval(() => {
            const startTime = new Date(jobData.overall_start_time).getTime();
            if (isNaN(startTime) || startTime <= 0) return;
            durationSpan.textContent = Math.max(0, (Date.now() - startTime) / 1000).toFixed(2) + 's';
        }, 100);
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
    timingInfoEl.classList.remove("hidden");
    document.querySelector("#start-time").textContent = jobData.overall_start_time ? new Date(jobData.overall_start_time).toLocaleTimeString() : 'N/A';
    
    if (jobData.status === 'completed' || jobData.status === 'failed') {
        document.querySelector("#end-time").textContent = jobData.overall_end_time ? new Date(jobData.overall_end_time).toLocaleTimeString() : 'N/A';
        document.querySelector("#duration").textContent = jobData.overall_duration || 'N/A';
        if (timingIntervalId) { clearInterval(timingIntervalId); timingIntervalId = null; }
    } else {
        document.querySelector("#end-time").textContent = 'Running...';
        if (timingIntervalId) clearInterval(timingIntervalId);
        timingIntervalId = setInterval(() => {
            const job = activeJobs[currentTimingJobId];
            if (!job) return;
            if (job.status === 'completed' || job.status === 'failed') {
                document.querySelector("#duration").textContent = job.overall_duration || 'N/A';
                document.querySelector("#end-time").textContent = job.overall_end_time ? new Date(job.overall_end_time).toLocaleTimeString() : 'N/A';
                clearInterval(timingIntervalId); timingIntervalId = null;
                return;
            }
            const startTime = new Date(job.overall_start_time).getTime();
            if (isNaN(startTime) || startTime <= 0) return;
            document.querySelector("#duration").textContent = Math.max(0, (Date.now() - startTime) / 1000).toFixed(2) + 's';
        }, 100);
    }
}

function doOCR(){
    if (!state.file) { alert("Please select a file first."); return; }
    const resultEl = document.querySelector("#resulttext");
    resultEl.value = "Scanning..."; 
    document.querySelector('main').classList.add('scanning');
    const language = document.getElementById('source_lang').value;
    const jobId = 'sync-' + Date.now();
    const data = new FormData();
    data.append('file', state.file);
    data.append('language', language);
    data.append('job_id', jobId);
    
    activeJobs[jobId] = { job_id: jobId, status: 'in_progress', results: [], overall_start_time: new Date().toISOString(), overall_end_time: null, overall_duration: null, error: null, files: [{ filename: state.file.name, language: language }] };
    displayJob(jobId, activeJobs[jobId]);
    updateTimingInfoDisplay(jobId);
    startPolling();

    fetch('/api/ocr', { method: 'POST', body: data })
    .then(response => {
        document.querySelector('main').classList.remove('scanning');
        if (!response.ok) return response.json().then(err => { throw new Error(err.error || 'Server error'); });
        return response.json();
    })
    .then(result => {
        activeJobs[jobId] = { ...activeJobs[jobId], status: result.error ? 'failed' : 'completed', results: [{ ...result, filename: state.file.name }], overall_start_time: result.start_time || activeJobs[jobId].overall_start_time, overall_end_time: result.end_time || new Date().toISOString(), overall_duration: result.duration, error: result.error };
                displayJob(jobId, activeJobs[jobId]);
                updateTimingInfoDisplay(jobId);
        
                if (result.image_base64) {
                    resultEl.value = JSON.stringify(result, null, 2);
                    drawOCRData(result);
                } else {
                    // For PDF, result is the first element of an array in activeJobs, 
                    // but the fetch response itself might be the full object or array.
                    // Let's use the stored results array for consistency.
                    const resultsArray = activeJobs[jobId].results;
                    resultEl.value = JSON.stringify(resultsArray, null, 2);
                    drawOCRData(resultsArray);
                }
            })
    .catch(error => {
        document.querySelector('main').classList.remove('scanning');
        activeJobs[jobId] = { ...activeJobs[jobId], status: 'failed', overall_end_time: new Date().toISOString(), overall_duration: 'N/A', error: error.message || error };
        displayJob(jobId, activeJobs[jobId]);
        resultEl.value = `Error: ${error.message || error}`;
    });
}

async function submitAsyncOCR(){
    const uploadImageInput = document.querySelector("#uploadimage");
    const selectedFiles = uploadImageInput.files;
    if (selectedFiles.length === 0) { alert("Please select at least one file for asynchronous processing."); return; }
    document.querySelector('main').classList.add('scanning');
    const filesPayload = [];
    for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        const base64String = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = error => reject(error);
            reader.readAsDataURL(file);
        });
        filesPayload.push({ filename: file.name, base64: base64String, language: document.getElementById('source_lang').value });
    }

    try {
        const response = await fetch('/api/async_ocr', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: filesPayload }) });
        const jsonResponse = await response.json();
        document.querySelector('main').classList.remove('scanning');
        if (response.ok) {
            const jobId = jsonResponse.job_id;
            activeJobs[jobId] = { job_id: jobId, status: jsonResponse.status, results: [], overall_start_time: new Date().toISOString(), overall_end_time: null, overall_duration: null, error: null, files: filesPayload };
            displayJob(jobId, activeJobs[jobId]);
            updateTimingInfoDisplay(jobId);
            startPolling();
            document.querySelector("#resulttext").value = jsonResponse.message;
        }
    } catch (error) { document.querySelector('main').classList.remove('scanning'); console.error("Async submit error:", error); }
}
