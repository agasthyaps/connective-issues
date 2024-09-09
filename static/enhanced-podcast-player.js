// Function to convert Markdown-style bold to HTML bold
function convertMarkdownBold(text) {
    const final_text = text.replace(/\*\*(alex|jamie):\*\*/g, '<span class="speaker" style="font-weight:600;">$1:</span>');
    return final_text;
}

// Function to synchronize transcript scrolling with audio playback
function syncTranscriptScroll() {
    const audioPlayer = document.querySelector('audio');
    const transcript = document.getElementById('finalScriptShare');
    
    if (!audioPlayer || !transcript) return;

    audioPlayer.addEventListener('timeupdate', () => {
        const progress = audioPlayer.currentTime / audioPlayer.duration;
        const scrollPosition = (transcript.scrollHeight - transcript.clientHeight) * progress;
        transcript.scrollTop = scrollPosition;
    });
}

// Function to initialize everything when the DOM is loaded
function init() {
    const transcript = document.getElementById('finalScriptShare');
    if (transcript) {
        transcript.innerHTML = convertMarkdownBold(transcript.innerHTML);
    }
    syncTranscriptScroll();
}

// Run initialization when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', init);