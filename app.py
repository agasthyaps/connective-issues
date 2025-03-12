import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory, session, make_response, url_for, send_file
from flask_socketio import SocketIO, emit, disconnect
from werkzeug.utils import secure_filename
import os
import time
from prompts import *
from utils import *
import random
from google.cloud import storage
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import db_helpers
import string
import logging
import tempfile
from threading import Thread
from migrate_db import migrate_expiration_dates


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')  # Use environment variable in production
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=20)  # Increase to 20 minutes
socketio = SocketIO(app)
logging.basicConfig(level=logging.DEBUG)
app_ready = False

# Configure folders
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
STATIC_FOLDER = os.path.join(app.root_path, 'static')
TEMP_FOLDER = tempfile.mkdtemp()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the necessary folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# Server-side storage
server_side_storage = {}

# Initialize necessary components
podteam = {}
made_one = False

def initialize_app():
    global app_ready
    # Initialize the database
    db_helpers.init_db()

    if os.environ.get('RUN_MIGRATION', 'false').lower() == 'true':
        migrate_expiration_dates()

    # Set up the scheduler for cleanup
    scheduler = BackgroundScheduler()
    scheduler.add_job(db_helpers.cleanup_expired_podcasts, 'interval', hours=24)
    scheduler.start()

    app_ready = True

def generate_share_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

@app.route('/get_podcasts_remaining', methods=['GET'])
def get_podcasts_remaining():
    podcasts_remaining = request.cookies.get('podcasts_remaining')
    if podcasts_remaining is None:
        podcasts_remaining = 5
    else:
        podcasts_remaining = int(podcasts_remaining)
    return jsonify({'podcasts_remaining': podcasts_remaining})

@app.before_first_request
def before_first_request():
    global app_ready
    if not app_ready:
        thread = Thread(target=initialize_app)
        thread.start()

@app.route('/')
def loading():
    return render_template('loading.html')

@app.route('/check-ready')
def check_ready():
    return jsonify({'ready': app_ready})

@app.route('/main')
def main():
    global podteam
    # re-initialize the podteam every time the main page is loaded
    podteam = {
        'summarizer': initialize_chain('opus', summarizer_system_prompt),
        'type_classifier': initialize_chain('gpt', convo_type_system_prompt),
        'outliner': initialize_chain('omni', outliner_system_prompt),
        'scripter': initialize_chain('opus', scripter_system_prompt, history=True),
        'feedback_giver': initialize_chain('opus', feedback_system_prompt, history=True),
        'casual_editor': initialize_chain('haiku', NEW_CASUAL_PROMPT, history=True),
        'multi_summarizer': initialize_chain('opus', multi_summary_system_prompt),
        'titler': initialize_chain('gpt', titler_system_prompt)
    }
    podcasts_remaining = request.cookies.get('podcasts_remaining')
    if podcasts_remaining is None:
        podcasts_remaining = 5
        response = make_response(render_template('index.html', podcasts_remaining=podcasts_remaining))
        set_cookie_with_samesite(response, 'podcasts_remaining', str(podcasts_remaining), max_age=30*24*60*60)
        return response
    else:
        podcasts_remaining = int(podcasts_remaining)
    return render_template('index.html', podcasts_remaining=podcasts_remaining)

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/upload', methods=['POST'])
def upload():
    global TESTING
    pdfs = []
    uploaded_files = []
    theme = request.form.get('theme', '')
    podcasts_remaining = request.cookies.get('podcasts_remaining')
    
    if podcasts_remaining is None:
        podcasts_remaining = 5
    else:
        podcasts_remaining = int(podcasts_remaining)

    if podcasts_remaining <= 0:
        return jsonify({'error': 'You have reached the maximum number of podcast generations', 'podcasts_remaining': 0}), 403

    
    session_id = str(uuid.uuid4())  # Generate a unique session ID

    # if TESTING:
    #     print("Testing mode: returning dummy data")
    #     socketio.start_background_task(create_podcast, session_id, pdfs, theme)
    #     return jsonify({'message': 'Podcast creation started', 'session_id': session_id})
    # else:
    print("we shouldn't be here")
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
        server_side_storage[session_id] = {'uploaded_files': uploaded_files}

        # Start the podcast creation process in a background task
        socketio.start_background_task(create_podcast, session_id, pdfs, theme)

        podcasts_remaining -= 1
        response = jsonify({
            'message': 'Podcast creation started', 
            'session_id': session_id, 
            'podcasts_remaining': podcasts_remaining
        })
        set_cookie_with_samesite(response, 'podcasts_remaining', str(podcasts_remaining), max_age=15*60)
        return response
    except Exception as e:
        print(f"Error in upload: {str(e)}")
        return jsonify({'error': 'An error occurred during file upload'}), 500
    
def create_podcast(session_id, pdfs, theme):
    global TESTING, made_one
    # if TESTING:
    #     print(f"Creating podcast for session ID: {session_id}")
    #     time.sleep(1)
    #     print("Testing mode: CREATE PODCAST")
    #     socketio.emit('complete', {
    #         'audio_path': f'podcast_179.mp3',
    #         'script': test_post,
    #         'session_id': session_id
    #     })
    # else:
    addl_prompt = ""
    if theme:
        addl_prompt = f"As you read and think, keep in mind that the podcast episode MUST be about {theme}."
    try:
        socketio.emit('update', {'data': 'Podcast production team started!','session_id': session_id})
        
        # Extract text from PDFs
        texts = []
        truncated_texts = []
        for file in pdfs:
            socketio.emit('update', {'data': f"📚 reading through {os.path.basename(file['pdf'])}",'session_id': session_id})
            text = extract_text_from_pdf(file['pdf'])
            if file['kind'] =='me':
                addl_prompt = addl_prompt + "This piece was submitted by a listener. It may be an article, notes, a brainstorm, or something else entirely. Treat their thoughts seriously and try to make sense of them, especially in the context of any theme you may be focusing on."
            processed_text = addl_prompt + text
            truncated_text = text[:15000]
            texts.append(processed_text)
            truncated_texts.append(truncated_text)

        # Store the processed texts and theme in the session storage
        if session_id in server_side_storage:
            server_side_storage[session_id]['processed_texts'] = texts
            server_side_storage[session_id]['theme'] = theme
        else:
            server_side_storage[session_id] = {
                'processed_texts': texts,
                'theme': theme
            }
        
        # Summarize articles
        summaries = []
        for i, text in enumerate(texts):
            socketio.emit('update', {'data': f"🔬 research team is summarizing article {i+1}",'session_id': session_id})
            summary = conversation_engine(podteam['summarizer'], text)
            summaries.append(summary)
        
        # Create multi-article summary if necessary
        if len(summaries) > 1:
            socketio.emit('update', {'data': "🔗 research team is finding connections",'session_id': session_id})
            joined_summaries = f"{theme}\n" + "\n".join(summaries) if theme else "\n".join(summaries)
            final_summary = conversation_engine(podteam['multi_summarizer'], joined_summaries)
        else:
            final_summary = summaries[0]
        
        final_text = "\n".join(texts)
        final_truncated_text = "\n".join(truncated_texts)

        # TEST: classify the conversation type
        # conversation_type = conversation_engine(podteam['type_classifier'], final_summary)
        # logging.info(f"Conversation type: {conversation_type}")
        
        # Create outline
        socketio.emit('update', {'data': "✍️ writers creating outline",'session_id': session_id})
        outline = conversation_engine(podteam['outliner'], f"{theme}\nARTICLE(s):\n {final_text}\nSUMMARY:\n {final_summary}")
        
        # Create first script
        socketio.emit('update', {'data': "✍️ writers creating first draft script",'session_id': session_id})
        script = conversation_engine(podteam['scripter'], f"ARTICLE(s) EXCERPT(s):\n {final_truncated_text}\nOUTLINE:\n {outline}")
        
        # Revise script
        for i in range(1):  # Adjust the number of revisions as needed
            socketio.emit('update', {'data': f"👓 editors revising draft",'session_id': session_id})
            feedback = conversation_engine(podteam['feedback_giver'], f"{theme}\nSCRIPT:\n {script}")
            script = conversation_engine(podteam['scripter'], f"You received feedback. Here is the feedback:\n {feedback}\n{theme}")
        
        # Create casual script
        socketio.emit('update', {'data': "👨‍🏫 making script more human",'session_id': session_id})
        casual_script = process_casual_dialogue(script, podteam['casual_editor'])

        # Format the script
        formatted_script = format_script(casual_script)
        title = conversation_engine(podteam['titler'], formatted_script)
        script_with_title = f"<h2>{title}</h2>\n\n{formatted_script}"
        
        # Create audio (you'll need to implement this part based on your existing code)
        socketio.emit('update', {'data': "🎙️ recording the pod",'session_id': session_id})
        audio_path = create_podcast_from_script(casual_script, TEMP_FOLDER, STATIC_FOLDER, app.root_path)
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Final audio file not created: {audio_path}")

        audio_filename = os.path.basename(audio_path)
        local_audio_path = os.path.join(STATIC_FOLDER, audio_filename)
    
        # Save to GCS and get the blob name
        blob_name = db_helpers.save_shared_podcast(session_id, local_audio_path, script_with_title)

        # Emit the complete event with the share_id instead of a full URL
        socketio.emit('complete', {
            'share_id': session_id,
            'script': formatted_script,
            'session_id': session_id,
            'blob_name': blob_name,
            'title': title
        })

        made_one = True

    except Exception as e:
        print(f"Error in create_podcast: {str(e)}")
        socketio.emit('error', {'data': str(e), 'session_id': session_id})

@app.route('/generate_blog', methods=['POST'])
def generate_blog():
    global TESTING
    if TESTING:
        time.sleep(2)
        return jsonify({'blog_post': test_post})
    else:
        try:
            data = request.json
            session_id = data.get('session_id')
            
            if session_id not in server_side_storage:
                return jsonify({'error': 'Invalid session ID'}), 400
            
            session_data = server_side_storage[session_id]
            processed_texts = session_data.get('processed_texts', [])
            theme = session_data.get('theme', '')
            
            if not processed_texts:
                return jsonify({'error': 'No processed texts found for this session'}), 400
            
            model = random.choice(['4o', 'opus'])
            
            # Combine processed texts and theme
            combined_input = f"Write an engaging blog post for a knowledgeable but casual audience. Only output the post. Theme: {theme}\n\nContent:\n" + "\n\n".join(processed_texts)
            
            # Generate blog post using the 'opus' model and blogger_system_prompt
            blog_post = conversation_engine(
                initialize_chain(model, blogger_system_prompt),
                combined_input
            )

            if session_id in server_side_storage:
                server_side_storage[session_id]['blogger_model'] = model
            
            return jsonify({'blog_post': blog_post})
        except Exception as e:
            print(f"Error in generate_blog: {str(e)}")
            return jsonify({'error': 'An error occurred during blog generation'}), 500

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        if TESTING:
            feedback_entry = {
                'timestamp': datetime.now().isoformat(),
                'choice': 'bla',
                'feedback': 'blabla',
                'model': 'test'
            }
        else:
            data = request.json
            choice = data.get('choice')
            feedback = data.get('feedback', '')        
            session_id = data.get('session_id')
            model = server_side_storage[session_id].get('blogger_model', '')

            # Create a feedback entry
            feedback_entry = {
                'timestamp': datetime.now().isoformat(),
                'choice': choice,
                'feedback': feedback,
                'model': model
            }

        # Convert the feedback entry to JSON
        feedback_json = json.dumps(feedback_entry)

        # Generate a unique filename using timestamp
        filename = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Get the bucket
        bucket = db_helpers.storage_client.bucket(db_helpers.bucket_name)

        # Create a new blob and upload the feedback
        blob = bucket.blob(f"feedback/{filename}")
        blob.upload_from_string(feedback_json, content_type='application/json')

        return jsonify({'message': 'Feedback submitted successfully'})
    except Exception as e:
        print(f"Error in submit_feedback: {str(e)}")
        return jsonify({'error': 'An error occurred while submitting feedback'}), 500
    
@app.route('/generate_share_link', methods=['POST'])
def generate_share_link():
    try:
        data = request.json
        share_id = data.get('share_id')
        
        if not share_id:
            raise ValueError("Invalid share ID")
        
        podcast = db_helpers.get_shared_podcast(share_id)
        if not podcast:
            raise ValueError("Podcast not found")
        
        share_url = f'/shared/{share_id}'
        
        return jsonify({'share_url': share_url}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/audio/<share_id>')
def serve_audio(share_id):
    podcast = db_helpers.get_shared_podcast(share_id)
    if podcast:
        storage_client = storage.Client()
        bucket = storage_client.bucket(os.environ.get('GCS_BUCKET_NAME'))
        blob = bucket.blob(podcast['gcs_blob_name'])
        
        # Download the file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        blob.download_to_filename(temp_file.name)
        
        return send_file(temp_file.name, mimetype='audio/mpeg', as_attachment=True, download_name=f"{share_id}.mp3")
    else:
        return "Podcast not found or has expired", 404

@app.route('/shared/<share_id>')
def shared_podcast(share_id):
    podcast = db_helpers.get_shared_podcast(share_id)
    if podcast:
        logging.info(f"Shared podcast found, app.py: {share_id}")
        audio_url = url_for('serve_audio', share_id=share_id, _external=True)
        return render_template('shared_podcast.html', 
                               audio_url=audio_url, 
                               transcript=podcast['transcript'])
    else:
        return "Podcast not found or has expired", 404

def set_cookie_with_samesite(response, name, value, max_age):
    response.set_cookie(name, value, max_age=max_age, samesite='Lax', secure=True, httponly=True)

@app.route('/api/create_podcast', methods=['POST'])
def api_create_podcast():
    try:
        # Validate request
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 415
        
        data = request.json
        notes = data.get('notes')
        if not notes:
            return jsonify({'error': 'Outline is required'}), 400
            
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Initialize API-specific podteam
        api_podteam = {
            'scripter': initialize_chain('omni', wander_scripter_system_prompt, history=True),
            'casual_editor': initialize_chain('4o', NEW_CASUAL_PROMPT),
        }
        
        # Create first script
        script = conversation_engine(api_podteam['scripter'], f"NOTES:\n{notes}")
        
        # Create casual script
        casual_script = process_casual_dialogue(script, api_podteam['casual_editor'])
        
        # Create audio
        audio_path = create_podcast_from_script(casual_script, TEMP_FOLDER, STATIC_FOLDER, app.root_path, wander=True)
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Final audio file not created: {audio_path}")

        audio_filename = os.path.basename(audio_path)
        local_audio_path = os.path.join(STATIC_FOLDER, audio_filename)
        
        # Save to GCS and get the blob name
        blob_name = db_helpers.save_shared_podcast(session_id, local_audio_path, casual_script)
        
        # Get the audio URL
        storage_client = storage.Client()
        bucket = storage_client.bucket(os.environ.get('GCS_BUCKET_NAME'))
        blob = bucket.blob(blob_name)
        
        audio_url = url_for('serve_audio', share_id=session_id, _external=True)
        
        return jsonify({
            'success': True,
            'audio_url': audio_url,
            'script': casual_script,
            'session_id': session_id
        })
        
    except Exception as e:
        print(f"Error in api_create_podcast: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        # Clean up temporary files
        try:
            if 'audio_path' in locals() and os.path.exists(audio_path):
                os.remove(audio_path)
            if 'local_audio_path' in locals() and os.path.exists(local_audio_path):
                os.remove(local_audio_path)
        except Exception as e:
            print(f"Error cleaning up files: {str(e)}")

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.args.get('session_id')
    if session_id and session_id in server_side_storage:
        try:
            # Delete podcast file
            podcast_path = server_side_storage[session_id].get('podcast_path')
            if podcast_path and os.path.exists(podcast_path):
                os.remove(podcast_path)
                print(f"Deleted podcast file: {podcast_path}")

            # Delete uploaded PDF files
            uploaded_files = server_side_storage[session_id].get('uploaded_files', [])
            for file_path in uploaded_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted uploaded file: {file_path}")

            # Clear storage data
            del server_side_storage[session_id]
            print(f"Cleared storage data for session {session_id}")

        except Exception as e:
            print(f"Error in handle_disconnect: {str(e)}")

    disconnect()  # Ensure the client is disconnected


