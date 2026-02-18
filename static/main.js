const droparea = document.querySelector(".drop")
const input = document.querySelector("#uploadimage")

state = {
    isDragging: false,
    wrongFile: false,
    file: null
}

input.addEventListener("change", () => {
    const files = input.files
    onDrop(files[0]);
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
    }
    if (file.type.indexOf("application/pdf") >= 0) {
        state.file=file
        displayPdf()
    }
}

droparea.addEventListener("drop", (e) => {
    e.preventDefault()
    const files = e.dataTransfer.files;
    onDrop(files[0])
})

document.querySelector("#ocr-img").addEventListener("drop", (e) => {
    e.preventDefault()
    const files = e.dataTransfer.files;
    onDrop(files[0])
})

droparea.addEventListener("dragover", (event) => {
    // prevent default to allow drop
    event.preventDefault();
  });

document.onpaste = (event) => {
    event.preventDefault();
    var items = event.clipboardData?.items;
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
        }
    }
};

function doOCR(){
    const resultEl = document.querySelector("#resulttext")
    var data = new FormData()
    const language = document.getElementById('source_lang').value;
    data.append('file', state.file)
    data.append('language',language)
    resultEl.value  = "Scanning..."

    const startTime = new Date();
    const timingInfoEl = document.querySelector("#timing-info");
    const startTimeEl = document.querySelector("#start-time");
    const endTimeEl = document.querySelector("#end-time");
    const durationEl = document.querySelector("#duration");

    timingInfoEl.classList.remove("hidden");
    timingInfoEl.style.display = 'block'; // Explicitly set display to block
    startTimeEl.textContent = startTime.toLocaleTimeString();
    endTimeEl.textContent = "";
    durationEl.textContent = "";

    fetch('/api/ocr', {
      method: 'POST',
      body: data
    })
    .then(response => response.json())
    .then(result => {
        // Updated to use server-provided timing info
        const startTimeISO = result.start_time;
        const endTimeISO = result.end_time;
        const durationValue = result.duration;

        if (startTimeISO) {
            startTimeEl.textContent = new Date(startTimeISO).toLocaleTimeString();
        }
        if (endTimeISO) {
            endTimeEl.textContent = new Date(endTimeISO).toLocaleTimeString();
        }
        if (durationValue) {
            durationEl.textContent = durationValue;
        }
        
        resultEl.value = result.error || result.text;
    })
    .catch(() => { /* Error. Inform the user */ })
}