from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_socketio import SocketIO, emit, disconnect
from werkzeug.utils import secure_filename
import os
import time
from prompts import *
from utils import *

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')  # Use environment variable in production
socketio = SocketIO(app)

# Configure folders
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
TEMP_FOLDER = os.path.join(app.root_path, 'temp')
STATIC_FOLDER = os.path.join(app.root_path, 'static')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the necessary folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# Initialize necessary components (you'll need to adapt these based on your existing code)
summarizer = initialize_chain('gpt', summarizer_system_prompt)
outliner = initialize_chain('opus', outliner_system_prompt)
scripter = initialize_chain('gpt', scripter_system_prompt, history=True)
feedback_giver = initialize_chain('opus', feedback_system_prompt, history=True)
casual_editor = initialize_chain('gpt', casual_system_prompt)
multi_summarizer = initialize_chain('opus', multi_summary_system_prompt)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    pdfs = []
    for i in range(4):  # Allow up to 4 PDFs
        if f'pdf_{i}' in request.files:
            file = request.files[f'pdf_{i}']
            if file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                pdfs.append({
                    'pdf': filepath,
                    'kind': request.form[f'kind_{i}']
                })
    
    theme = request.form.get('theme', '')
    
    # Start the podcast creation process in a background task
    socketio.start_background_task(create_podcast, pdfs, theme)
    
    return jsonify({'message': 'Podcast creation started'})

def create_podcast(pdfs, theme):
    if theme:
        addl_prompt = f"As you read and think, keep in mind that the podcast episode MUST be about {theme}."
    else:
        addl_prompt = ""
    try:
        socketio.emit('update', {'data': 'Starting podcast creation process'})
        
        # Extract text from PDFs
        texts = []
        truncated_texts = []
        for file in pdfs:
            socketio.emit('update', {'data': f"Extracting text from {os.path.basename(file['pdf'])}"})
            text = extract_text_from_pdf(file['pdf'])
            text = addl_prompt + text
            truncated_text = text[:15000]
            texts.append(text)
            truncated_texts.append(truncated_text)
        
        # Summarize articles
        summaries = []
        for i, text in enumerate(texts):
            socketio.emit('update', {'data': f"Summarizing article {i+1}"})
            summary = conversation_engine(summarizer, text)
            summaries.append(summary)
        
        # Create multi-article summary if necessary
        if len(summaries) > 1:
            socketio.emit('update', {'data': "Creating multi-article summary"})
            joined_summaries = f"{theme}\n" + "\n".join(summaries) if theme else "\n".join(summaries)
            final_summary = conversation_engine(multi_summarizer, joined_summaries)
        else:
            final_summary = summaries[0]
        
        final_text = "\n".join(texts)
        final_truncated_text = "\n".join(truncated_texts)
        
        # Create outline
        socketio.emit('update', {'data': "Creating outline"})
        outline = conversation_engine(outliner, f"{theme}\nARTICLE(s):\n {final_text}\nSUMMARY:\n {final_summary}")
        
        # Create first script
        socketio.emit('update', {'data': "Creating first script"})
        script = conversation_engine(scripter, f"ARTICLE(s) EXCERPT(s):\n {final_truncated_text}\nOUTLINE:\n {outline}")
        
        # Revise script
        for i in range(1):  # Adjust the number of revisions as needed
            socketio.emit('update', {'data': f"Revising script (round {i+1})"})
            feedback = conversation_engine(feedback_giver, f"{theme}\nSCRIPT:\n {script}")
            script = conversation_engine(scripter, f"You received feedback. Here is the feedback:\n {feedback}\n{theme}")
        
        # Create casual script
        socketio.emit('update', {'data': "Editing for natural conversation flow"})
        casual_script = conversation_engine(casual_editor, script)
        
        # Create audio (you'll need to implement this part based on your existing code)
        socketio.emit('update', {'data': "Creating audio"})
        audio_path = create_podcast_from_script(casual_script, TEMP_FOLDER, STATIC_FOLDER, app.root_path)
        
        # Get the filename from the full path
        audio_filename = os.path.basename(audio_path)

        session[request.sid] = {'podcast_path': audio_path}


        # Emit final results
        socketio.emit('complete', {
            'audio_path': f'/audio/{audio_filename}',  # Use the route we'll define next
            'script': casual_script
        })

    except Exception as e:
        socketio.emit('error', {'data': str(e)})

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(STATIC_FOLDER, filename)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in session:
        podcast_path = session[sid].get('podcast_path')
        if podcast_path and os.path.exists(podcast_path):
            os.remove(podcast_path)
        session.pop(sid, None)

if __name__ == '__main__':
    socketio.run(app, debug=True)