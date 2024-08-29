import uuid
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

# Server-side storage
storage = {}

# Initialize necessary components
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
    uploaded_files = []
    theme = request.form.get('theme', '')
    
    session_id = str(uuid.uuid4())  # Generate a unique session ID

    try:
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
                    uploaded_files.append(filepath)

        # Store uploaded files in server-side storage
        storage[session_id] = {'uploaded_files': uploaded_files}

        # Start the podcast creation process in a background task
        socketio.start_background_task(create_podcast, session_id, pdfs, theme)

        return jsonify({'message': 'Podcast creation started', 'session_id': session_id})
    except Exception as e:
        print(f"Error in upload: {str(e)}")
        return jsonify({'error': 'An error occurred during file upload'}), 500
    
def create_podcast(session_id, pdfs, theme):
    if theme:
        addl_prompt = f"As you read and think, keep in mind that the podcast episode MUST be about {theme}."
    else:
        addl_prompt = ""
    try:
        socketio.emit('update', {'data': 'Podcast production team started!'})
        
        # Extract text from PDFs
        texts = []
        truncated_texts = []
        for file in pdfs:
            socketio.emit('update', {'data': f"📚 reading through {os.path.basename(file['pdf'])}"})
            text = extract_text_from_pdf(file['pdf'])
            text = addl_prompt + text
            truncated_text = text[:15000]
            texts.append(text)
            truncated_texts.append(truncated_text)
        
        # Summarize articles
        summaries = []
        for i, text in enumerate(texts):
            socketio.emit('update', {'data': f"🔬 research team is summarizing article {i+1}"})
            summary = conversation_engine(summarizer, text)
            summaries.append(summary)
        
        # Create multi-article summary if necessary
        if len(summaries) > 1:
            socketio.emit('update', {'data': "🔗 research team is finding connections"})
            joined_summaries = f"{theme}\n" + "\n".join(summaries) if theme else "\n".join(summaries)
            final_summary = conversation_engine(multi_summarizer, joined_summaries)
        else:
            final_summary = summaries[0]
        
        final_text = "\n".join(texts)
        final_truncated_text = "\n".join(truncated_texts)
        
        # Create outline
        socketio.emit('update', {'data': "✍️ writers creating outline"})
        outline = conversation_engine(outliner, f"{theme}\nARTICLE(s):\n {final_text}\nSUMMARY:\n {final_summary}")
        
        # Create first script
        socketio.emit('update', {'data': "✍️ writers creating first script"})
        script = conversation_engine(scripter, f"ARTICLE(s) EXCERPT(s):\n {final_truncated_text}\nOUTLINE:\n {outline}")
        
        # Revise script
        for i in range(1):  # Adjust the number of revisions as needed
            socketio.emit('update', {'data': f"👓 editors revising script (round {i+1})"})
            feedback = conversation_engine(feedback_giver, f"{theme}\nSCRIPT:\n {script}")
            script = conversation_engine(scripter, f"You received feedback. Here is the feedback:\n {feedback}\n{theme}")
        
        # Create casual script
        socketio.emit('update', {'data': "👨‍🏫 making script more human"})
        casual_script = conversation_engine(casual_editor, script)
        
        # Create audio (you'll need to implement this part based on your existing code)
        socketio.emit('update', {'data': "🎙️ recording the pod"})
        # When the podcast is created:
        audio_path = create_podcast_from_script(casual_script, TEMP_FOLDER, STATIC_FOLDER, app.root_path)
        audio_filename = os.path.basename(audio_path)

        # Store the podcast path in server-side storage
        if session_id in storage:
            storage[session_id]['podcast_path'] = audio_path

        # Emit final results
        socketio.emit('complete', {
            'audio_path': f'/audio/{audio_filename}',
            'script': casual_script,
            'session_id': session_id
        })

    except Exception as e:
        socketio.emit('error', {'data': str(e), 'session_id': session_id})

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(STATIC_FOLDER, filename)

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.args.get('session_id')
    if session_id and session_id in storage:
        try:
            # Delete podcast file
            podcast_path = storage[session_id].get('podcast_path')
            if podcast_path and os.path.exists(podcast_path):
                os.remove(podcast_path)
                print(f"Deleted podcast file: {podcast_path}")

            # Delete uploaded PDF files
            uploaded_files = storage[session_id].get('uploaded_files', [])
            for file_path in uploaded_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted uploaded file: {file_path}")

            # Clear storage data
            del storage[session_id]
            print(f"Cleared storage data for session {session_id}")

        except Exception as e:
            print(f"Error in handle_disconnect: {str(e)}")

    disconnect()  # Ensure the client is disconnected