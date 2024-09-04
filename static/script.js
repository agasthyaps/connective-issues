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
    let podcastsRemaining = 5; // Default value

    const helpMeTestBtn = document.getElementById('helpMeTest');
    const blogSection = document.getElementById('blogSection');
    const blogContainer = document.querySelector('.blog-container');
    const blogPost = document.getElementById('blogPost');
    const comparisonSection = document.getElementById('comparisonSection');
    const feedbackForm = document.querySelector('.feedback-form');
    const podcastMoreUsefulBtn = document.getElementById('podcastMoreUseful');
    const blogMoreUsefulBtn = document.getElementById('blogMoreUseful');
    const feedbackText = document.getElementById('feedbackText');
    const submitFeedbackBtn = document.getElementById('submitFeedback');
    const blogLoadingAnimation = document.getElementById('blogLoadingAnimation');

    let currentSessionId = null;
    let pdfCount = 1;
    let podcastCreated = false;

    function scrollToBottom() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }

    function setContentLayout(showBlog = false) {
        const comparisonEl = document.querySelector('.content-comparison');
        const scriptContainer = document.querySelector('.script-container');
        
        if (showBlog) {
            comparisonEl.classList.add('show-blog');
            scriptContainer.style.width = '48%';
            showElement(blogContainer);
        } else {
            comparisonEl.classList.remove('show-blog');
            scriptContainer.style.width = '100%';
            hideElement(blogContainer);
        }
    }

    helpMeTestBtn.addEventListener('click', function() {
        generateBlog();
        setContentLayout(true);
    });

    podcastMoreUsefulBtn.addEventListener('change', function(){
        showFeedbackForm();
        scrollToBottom();
    });
    blogMoreUsefulBtn.addEventListener('change', function(){
        showFeedbackForm();
        scrollToBottom();
    });
    submitFeedbackBtn.addEventListener('click', submitFeedback);

    function showBlogPost(blogContent) {
        hideElement(blogLoadingAnimation);
        blogPost.innerHTML = blogContent;
        showElement(blogPost);
        showElement(document.querySelector('.blog-container'));
        
        // Ensure the content comparison maintains the correct layout
        const contentComparison = document.querySelector('.content-comparison');
        contentComparison.style.display = 'flex';
        
        // Force a reflow to ensure the layout is applied correctly
        void contentComparison.offsetWidth;
        
        showElement(comparisonSection);
        scrollToBottom();
    }
    
    function generateBlog() {
        if (!currentSessionId) {
            console.error('No session ID available');
            return;
        }
        showElement(document.querySelector('.blog-container'));
        showElement(blogLoadingAnimation);
        hideElement(blogPost);
        hideElement(comparisonSection);
    
        // Reset layout
        const contentComparison = document.querySelector('.content-comparison');
        contentComparison.style.display = 'flex';
    
        fetch('/generate_blog', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error generating blog:', data.error);
                return;
            }
            showBlogPost(data.blog_post);
        })
        .catch(error => {
            console.error('Error:', error);
            hideElement(blogLoadingAnimation);
        });
    }
    
    // Helper functions
    function showElement(element) {
        if (element) element.classList.remove('hidden');
    }
    
    function hideElement(element) {
        if (element) element.classList.add('hidden');
    }

    function showFeedbackForm() {
        showElement(feedbackForm);
    }

    function submitFeedback() {
        const choice = document.querySelector('input[name="comparison"]:checked').value;
        const feedback = feedbackText.value;

        if (!currentSessionId) {
            console.error('No session ID available');
            return;
        }

        fetch('/submit_feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ choice: choice, feedback: feedback, session_id: currentSessionId }),
        })
        .then(response => response.json())
        .then(data => {
            console.log('Feedback submitted:', data);
            hideElement(feedbackForm);
            hideElement(comparisonSection);
            feedbackText.value = '';
        })
        .catch(error => console.error('Error:', error));
    }

    if (podcastsRemainingElement) {
        const remainingText = podcastsRemainingElement.textContent.split(': ')[1];
        podcastsRemaining = parseInt(remainingText) || 5;
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

            newInput.querySelector('.add-more-btn').addEventListener('click', addMoreInputs);
        }
        if (pdfCount === 4) {
            document.querySelectorAll('.add-more-btn').forEach(btn => btn.style.display = 'none');
        }
    }

    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (podcastsRemaining <= 0) {
                alert('You have reached the maximum number of podcast generations.');
                return;
            }
            const formData = new FormData(form);
            showElement(loadingAnimation);
            showElement(messages);
            currentStatus.textContent = 'Podcast creation started. Please wait...';
            
            setTimeout(() => {
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            }, 100);

            fetch('/upload', {
                method: 'POST',
                body: formData
            }).then(response => {
                if (!response.ok) {
                    throw response;
                }
                return response.json();
            })
            .then(data => {
                console.log(data);
                sessionId = data.session_id;
                podcastsRemaining = data.podcasts_remaining;
                updatePodcastsRemaining();
                initializeSocket(sessionId);
            }).catch(error => {
                if (error instanceof Response) {
                    error.json().then(errorData => {
                        console.error('Error:', errorData.error);
                        currentStatus.textContent = errorData.error;
                        currentStatus.classList.add('text-red-500');
                        showElement(messages);
                    });
                } else {
                    console.error('Error:', error);
                    currentStatus.textContent = 'An error occurred. Please try again.';
                    currentStatus.classList.add('text-red-500');
                    showElement(messages);
                }
                hideElement(loadingAnimation);
            });
        });
    } else {
        console.error('Form with id "uploadForm" not found');
    }

    function initializeSocket(sessionId) {
        socket = io({
            query: { session_id: sessionId }
        });

        socket.on('update', function(msg) {
            if (msg.session_id === sessionId) {
                currentStatus.textContent = msg.data;
            }
        });

        socket.on('complete', function(data) {
            if (data.session_id === sessionId) {
                currentSessionId = data.session_id;
                hideElement(loadingAnimation);
                hideElement(messages);
                showElement(result);
                setContentLayout(false);
                hideElement(comparisonSection);
                podcastAudio.src = data.audio_path;

                const formattedScript = data.script.replace(/\*\*(alex|jamie):\*\*/g, '<span class="speaker">$1:</span>');
                finalScript.innerHTML = formattedScript.replace(/\n/g, '<br>');

                preproductionZone.style.transition = 'max-height 0.5s ease-out, opacity 0.5s ease-out, margin-bottom 0.5s ease-out';
                preproductionZone.style.maxHeight = preproductionZone.scrollHeight + 'px';
                preproductionZone.style.opacity = '1';
                
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
                hideElement(loadingAnimation);
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