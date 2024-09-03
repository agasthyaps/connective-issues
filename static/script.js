document.addEventListener('DOMContentLoaded', (event) => {
    let socket;
    let sessionId;
    const form = document.getElementById('uploadForm');
    const addMoreBtn = document.querySelector('.add-more-btn');
    const pdfInputs = document.getElementById('pdfInputs');
    const loadingAnimation = document.getElementById('loadingAnimation');
    const messages = document.getElementById('messages');
    const currentStatus = document.getElementById('currentStatus');
    const result = document.getElementById('result');
    const finalScript = document.getElementById('finalScript');
    const podcastAudio = document.getElementById('podcastAudio');
    const downloadBtn = document.getElementById('downloadPodcast');
    const preproductionZone = document.getElementById('preproductionZone');
    const createPodcastBtn = document.getElementById('createPodcastBtn');
    const podcastsRemainingElement = document.getElementById('podcastsRemaining');
    let podcastsRemaining = 3; // Default value

    if (podcastsRemainingElement) {
        const remainingText = podcastsRemainingElement.textContent.split(': ')[1];
        podcastsRemaining = parseInt(remainingText) || 3; // Use 3 as fallback if parsing fails
    }

    function updatePodcastsRemaining() {
        console.log('Updating podcasts remaining:', podcastsRemaining);
        if (podcastsRemainingElement) {
            podcastsRemainingElement.innerHTML = `<b>podcast generations remaining: ${podcastsRemaining}</b>`;
        }
        if (podcastsRemaining <= 0) {
            createPodcastBtn.disabled = true;
            createPodcastBtn.textContent = 'Maximum podcasts reached';
        }
    }

    updatePodcastsRemaining();


    let pdfCount = 1;
    let podcastCreated = false;

    if (addMoreBtn) {
        addMoreBtn.addEventListener('click', addMoreInputs);
    }

    function addMoreInputs() {
        if (pdfCount < 4) {
            const newInput = document.createElement('div');
            newInput.classList.add('pdf-input');
            newInput.innerHTML = `
                <label for="pdf_${pdfCount}" class="file-label">choose file:</label>
                <input type="file" id="pdf_${pdfCount}" name="pdf_${pdfCount}" accept=".pdf" class="file-input">
                <select name="kind_${pdfCount}" class="styled-select">
                    <option value="someone">(someone else's thoughts)</option>
                    <option value="my">(my thoughts)</option>
                </select>
                <button type="button" class="add-more-btn">add more</button>
            `;
            pdfInputs.appendChild(newInput);
            pdfCount++;

            // Update event listener for the new "add more" button
            newInput.querySelector('.add-more-btn').addEventListener('click', addMoreInputs);
        }
        if (pdfCount === 4) {
            document.querySelectorAll('.add-more-btn').forEach(btn => btn.style.display = 'none');
        }
    }

    if (form) {
        console.log('Adding submit event listener to form');

        form.addEventListener('submit', (e) => {
            console.log('Form submitted');

            e.preventDefault();
            if (podcastsRemaining <= 0) {
                alert('You have reached the maximum number of podcast generations.');
                return;
            }
            const formData = new FormData(form);
            loadingAnimation.classList.remove('hidden');
            messages.classList.remove('hidden');
            currentStatus.textContent = 'Podcast creation started. Please wait...';
            fetch('/upload', {
                method: 'POST',
                body: formData
            }).then(response => response.json())
            .then(data => {
                console.log(data);
                sessionId = data.session_id;
                podcastsRemaining = Math.max(0, podcastsRemaining - 1);
                updatePodcastsRemaining();
                initializeSocket(sessionId);
            }).catch(error => {
                console.error('Error:', error);
                currentStatus.textContent = 'An error occurred. Please try again.';
                currentStatus.classList.add('text-red-500');
                messages.classList.remove('hidden');
            });
        });
    } else {
        console.error('Form with id "uploadForm" not found');
    }

    function initializeSocket(sessionId) {
        socket = io({
            query: {
                session_id: sessionId
            }
        });

        socket.on('update', function(msg) {
            if (msg.session_id === sessionId) {
                currentStatus.textContent = msg.data;
            }
        });

        socket.on('complete', function(data) {
            if (data.session_id === sessionId) {
                loadingAnimation.classList.add('hidden');
                messages.classList.add('hidden');
                result.classList.remove('hidden');
                podcastAudio.src = data.audio_path;

                const formattedScript = data.script.replace(/\*\*(alex|jamie):\*\*/g, '<span class="speaker">$1:</span>');
                finalScript.innerHTML = formattedScript.replace(/\n/g, '<br>');

                // Collapse the preproductionZone
                preproductionZone.style.transition = 'max-height 0.5s ease-out, opacity 0.5s ease-out, margin-bottom 0.5s ease-out';
                preproductionZone.style.maxHeight = preproductionZone.scrollHeight + 'px';
                preproductionZone.style.opacity = '1';
                
                // Trigger reflow
                preproductionZone.offsetHeight;

                preproductionZone.style.maxHeight = '0';
                preproductionZone.style.opacity = '0';
                preproductionZone.style.marginBottom = '0';
                preproductionZone.style.overflow = 'hidden';

                podcastAudio.addEventListener('timeupdate', function() {
                const percent = (podcastAudio.currentTime / podcastAudio.duration) * 100;
                const scrollPosition = (finalScript.scrollHeight - finalScript.clientHeight) * (percent / 100);
                finalScript.scrollTop = scrollPosition;
            });

            podcastCreated = true;
            }
        });

        socket.on('error', function(data) {
            if (data.session_id === sessionId) {
                loadingAnimation.classList.add('hidden');
                currentStatus.textContent = 'Error: ' + data.data;
                currentStatus.classList.add('text-red-500');
            }
        });
    }

    window.addEventListener('beforeunload', (event) => {
        if (podcastCreated) {
            event.preventDefault();
            event.returnValue = '';
            return 'Your podcast will be lost if you close this page. Are you sure you want to leave?';
        }
    });

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const audioSrc = podcastAudio.src;
            const link = document.createElement('a');
            link.href = audioSrc;
            link.download = 'connective_issues_podcast.mp3';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }
});