document.addEventListener('DOMContentLoaded', (event) => {
    const socket = io();
    const form = document.getElementById('uploadForm');
    const addMoreBtn = document.getElementById('addMore');
    const pdfInputs = document.getElementById('pdfInputs');
    const loadingAnimation = document.getElementById('loadingAnimation');
    const messages = document.getElementById('messages');
    const currentStatus = document.getElementById('currentStatus');
    const result = document.getElementById('result');
    const finalScript = document.getElementById('finalScript');
    const podcastAudio = document.getElementById('podcastAudio');
    const downloadBtn = document.getElementById('downloadPodcast');

    let pdfCount = 1;

    addMoreBtn.addEventListener('click', () => {
        if (pdfCount < 4) {
            const newInput = document.createElement('div');
            newInput.classList.add('pdf-input', 'flex', 'items-center', 'space-x-4');
            newInput.innerHTML = `
                <select class="flex-grow p-2 border rounded" name="kind_${pdfCount}">
                    <option value="journal">Journal Article</option>
                    <option value="news">News Article</option>
                    <option value="book">Book Chapter</option>
                </select>
                <input type="file" name="pdf_${pdfCount}" accept=".pdf" class="flex-grow p-2 border rounded">
            `;
            pdfInputs.appendChild(newInput);
            pdfCount++;
        }
        if (pdfCount === 4) {
            addMoreBtn.style.display = 'none';
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        fetch('/upload', {
            method: 'POST',
            body: formData
        }).then(response => response.json())
        .then(data => {
            console.log(data);
            loadingAnimation.classList.remove('hidden');
            messages.classList.remove('hidden');
            currentStatus.textContent = 'Podcast creation started. Please wait...';
        }).catch(error => {
            console.error('Error:', error);
            currentStatus.textContent = 'An error occurred. Please try again.';
            currentStatus.classList.add('text-red-500');
            messages.classList.remove('hidden');
        });
    });

    socket.on('update', function(msg) {
        currentStatus.textContent = msg.data;
    });

    socket.on('complete', function(data) {
        loadingAnimation.classList.add('hidden');
        messages.classList.add('hidden');
        result.classList.remove('hidden');
        podcastAudio.src = data.audio_path;
        finalScript.textContent = data.script;
        podcastCreated = true;
    });

    window.addEventListener('beforeunload', (event) => {
        if (podcastCreated) {
            event.preventDefault();
            // Chrome requires returnValue to be set
            event.returnValue = '';
            return 'Your podcast will be lost if you close this page. Are you sure you want to leave?';
        }
    });

    socket.on('error', function(data) {
        loadingAnimation.classList.add('hidden');
        currentStatus.textContent = 'Error: ' + data.data;
        currentStatus.classList.add('text-red-500');
    });

    downloadBtn.addEventListener('click', () => {
        const audioSrc = podcastAudio.src;
        const link = document.createElement('a');
        link.href = audioSrc;
        link.download = 'connective_issues_podcast.mp3';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
});