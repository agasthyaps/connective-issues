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
    const conversationTitle = document.getElementById('conversationTitle');
    let podcastsRemaining; // Default value

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

    /* Labs toggle */
    const labsToggle = document.getElementById('labsToggle');
    let useGoogleTTS = labsToggle ? labsToggle.checked : false;
    if (labsToggle) {
        labsToggle.addEventListener('change', function() {
            useGoogleTTS = labsToggle.checked;
            // Optional: visually indicate active state by toggling a class on the icon
            const iconLabel = document.querySelector('label[for="labsToggle"]');
            if (iconLabel) {
                if (useGoogleTTS) {
                    iconLabel.classList.add('active');
                } else {
                    iconLabel.classList.remove('active');
                }
            }
        });
    }

    let currentSessionId = null;
    let currentShareId = null;
    let pdfCount = 1;
    let podcastCreated = false;
    const sharePodcastBtn = document.getElementById('sharePodcast');
    
    if (sharePodcastBtn) {
        sharePodcastBtn.addEventListener('click', generateShareLink);
    }

    // Ensure this function is called when the podcast is created
    function updateAudioPlayer(audioPath) {
        const audioElement = document.getElementById('podcastAudio');
        if (audioElement) {
            audioElement.src = audioPath;
            
            const downloadButton = document.getElementById('downloadPodcast');
            if (downloadButton) {
                downloadButton.href = audioPath;
            }
        } else {
            console.error('Audio element not found');
        }
    }

    function generateShareLink() {
        if (!currentShareId) {
            console.error('No share ID available');
            alert('Unable to generate share link. Please try again.');
            return;
        }
    
        const audioElement = document.getElementById('podcastAudio');
        const audioSrc = audioElement.src;
        const transcript = finalScript.innerHTML;
    
        console.log('Generating share link for:', currentShareId);
        console.log('Audio src:', audioSrc);
    
        fetch('/generate_share_link', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                share_id: currentShareId,
                audio_src: audioSrc,
                transcript: transcript
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            console.log('Server response:', data);
            const shareUrl = window.location.origin + data.share_url;
            showShareModal(shareUrl);
        })
        .catch((error) => {
            console.error('Error:', error);
            alert('An error occurred while generating the share link. Please try again.');
        });
    }

    function showShareModal(shareUrl) {
        const modal = document.createElement('div');
        modal.className = 'share-modal';
        modal.innerHTML = `
            <div class="share-modal-content">
                <h2>share the synthesis</h2>
                <p style='font-size:1.25em;'>the point of the convo is for it to be a tool to get <b>you</b> to <b>your</b> eventual output -- not for it to be <b><i>the</i> output</b>.</p>
                <p>but: did it help you synthesize or spark some ideas? is there someone else who might get <b>just as excited as you are?</b> then share it.</p>
                <p>(<i>link valid for 3 days</i>)</p>
                <input type="text" value="${shareUrl}" readonly>
                <button id="copyShareLink">Copy Link</button>
                <button id="closeShareModal">Close</button>
            </div>
        `;
        document.body.appendChild(modal);

        const copyBtn = modal.querySelector('#copyShareLink');
        const closeBtn = modal.querySelector('#closeShareModal');
        const input = modal.querySelector('input');

        copyBtn.addEventListener('click', () => {
            input.select();
            document.execCommand('copy');
            copyBtn.textContent = 'Copied!';
            setTimeout(() => {
                copyBtn.textContent = 'Copy Link';
            }, 2000);
        });

        closeBtn.addEventListener('click', () => {
            document.body.removeChild(modal);
        });
    }

    function scrollToBottom() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }

    function updatePodcastsRemaining() {
        console.log('Updating podcasts remaining:', podcastsRemaining);
        if (podcastsRemainingElement && podcastsRemaining !== undefined) {
            podcastsRemainingElement.innerHTML = `<b>conversation generations remaining: ${podcastsRemaining}</b>`;
        }
        if (podcastsRemaining <= 0) {
            createPodcastBtn.disabled = true;
            createPodcastBtn.textContent = 'Maximum conversations reached';
        }
    }

    // Fetch the initial podcast count from the server
    fetch('/get_podcasts_remaining')
        .then(response => response.json())
        .then(data => {
            podcastsRemaining = data.podcasts_remaining;
            updatePodcastsRemaining();
        })
        .catch(error => {
            console.error('Error fetching podcast count:', error);
            podcastsRemaining = 5; // Fallback to default value
            updatePodcastsRemaining();
        });

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

    if (addMoreBtn) {
        addMoreBtn.addEventListener('click', addMoreInputs);
    }

    function addMoreInputs() {
        if (pdfCount < 4) {
            const newInput = document.createElement('div');
            newInput.classList.add('pdf-input');
            newInput.innerHTML = `
                <div class="file-upload-container">
                <div class="tooltip-container">
                  <label for="pdf_${pdfCount}" class="file-label">Choose file:</label>
                  <div class="tooltip">
                    upload something you're thinking about: an article, your notes, etc.
                  </div>
                </div>
                <input type="file" id="pdf_${pdfCount}" name="pdf_${pdfCount}" accept=".pdf" class="file-input">
              </div>
              
              <div class="radio-container">
                <span class="radio-label">*these are:</span>
                <div class="tooltip-container">
                  <div class="radio-group">
                    <label>
                      <input type="radio" name="kind_${pdfCount}" value="someone" checked>
                      someone else's thoughts
                    </label>
                    <label>
                      <input type="radio" name="kind_${pdfCount}" value="my">
                      my thoughts
                    </label>
                  </div>
                  <div class="tooltip">
                    let the ai team know where the ideas in this upload are from
                  </div>
                </div>
              </div>
              
              <div class="tooltip-container">
                <button type="button" class="add-more-btn" id="addmore_${pdfCount}">add more</button>
                <div class="tooltip">
                  add more content for the convo
                </div>
              </div>
              
              <span class="file-size-error hidden">File too large (max 10MB)</span>
            `;
            pdfInputs.appendChild(newInput);
            
            const fileInput = newInput.querySelector(`#pdf_${pdfCount}`);
            fileInput.addEventListener('change', validateFileSize);
            
            newInput.querySelector(`#addmore_${pdfCount}`).addEventListener('click', addMoreInputs);
            // hide old add more button
            hideElement(document.querySelector(`#addmore_${pdfCount - 1}`));
            
            pdfCount++;
        }
        
        if (pdfCount === 4) {
            document.querySelectorAll('.add-more-btn').forEach(btn => btn.style.display = 'none');
        }
    }

    function validateFileSize(event) {
        const file = event.target.files[0];
        const maxSizeInBytes = 10 * 1024 * 1024; // 10MB (as per the HTML)
        const pdfInput = event.target.closest('.pdf-input');
        const errorElement = pdfInput.querySelector('.file-size-error');
        
        if (errorElement) {
            if (file && file.size > maxSizeInBytes) {
                event.target.value = ''; // Clear the file input
                errorElement.classList.remove('hidden');
            } else {
                errorElement.classList.add('hidden');
            }
        } else {
            console.error('Error element not found');
        }
    }
    // Add event listener to the initial file input
    const initialFileInput = document.querySelector('#pdf_0');
    if (initialFileInput) {
        initialFileInput.addEventListener('change', validateFileSize);
    }

    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (podcastsRemaining <= 0) {
                alert('You have reached the maximum number of conversation generations.');
                return;
            }

            // Validate all file inputs before submitting
            const fileInputs = form.querySelectorAll('input[type="file"]');
            let isValid = true;

            fileInputs.forEach(input => {
                if (input.files[0] && input.files[0].size > 10 * 1024 * 1024) {
                    isValid = false;
                    const errorElement = input.parentElement.querySelector('.file-size-error');
                    errorElement.classList.remove('hidden');
                }
            });

            if (!isValid) {
                alert('Please ensure all files are under 10MB before submitting.');
                return;
            }

            const formData = new FormData(form);
            // Append labs toggle state
            formData.append('use_google', useGoogleTTS ? 'true' : 'false');
            showElement(loadingAnimation);
            showElement(messages);
            currentStatus.textContent = 'Conversation creation started. Please wait...';
            
            setTimeout(() => {
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            }, 100);

            fetch('/upload', {
                method: 'POST',
                body: formData
            }).then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                console.log(data);
                sessionId = data.session_id;
                podcastsRemaining = data.podcasts_remaining;
                updatePodcastsRemaining();
                initializeSocket(sessionId);
            }).catch(error => {
                console.error('Error:', error.message);
                currentStatus.textContent = error.message;
                currentStatus.classList.add('text-red-500');
                showElement(messages);
                if (error.podcasts_remaining !== undefined) {
                    podcastsRemaining = error.podcasts_remaining;
                    updatePodcastsRemaining();
                }
                hideElement(loadingAnimation);
            });

            // Disable labs toggle once podcast creation starts to prevent changes during processing
            if (labsToggle) {
                labsToggle.disabled = true;
            }
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
                currentShareId = data.share_id;  // Store the share_id
                hideElement(loadingAnimation);
                hideElement(messages);
                showElement(result);
                setContentLayout(false);
                hideElement(comparisonSection);
                
                // Construct the audio URL
                const audioPath = `/audio/${data.share_id}`;
                console.log('Updating audio player with:', audioPath);
                updateAudioPlayer(audioPath);

                // Normalize speaker labels for Google TTS scripts
                let normalizedScript = data.script.replace(/Speaker 1:/g, '**cam:**').replace(/Speaker 2:/g, '**sage:**');
                const formattedScript = normalizedScript.replace(/\*\*(cam|sage|expert):\*\*/g, '<span class="speaker">$1:</span>');
                finalScript.innerHTML = formattedScript.replace(/\n/g, '<br>');
                conversationTitle.textContent = data.title;

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
                updatePodcastsRemaining();
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
            return 'Your conversation will be lost if you close this page. Are you sure you want to leave?';
        }
    });

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const audioSrc = podcastAudio.src;
            const link = document.createElement('a');
            link.href = audioSrc;
            link.download = 'connective_issues_conversation.mp3';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }
});