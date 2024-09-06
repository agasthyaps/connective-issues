import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from openai import OpenAI
from pydub import AudioSegment
import pdfplumber
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import os
import random
import logging
import tempfile


# testing flag
TESTING = False

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
eleven_client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)

def extract_text_from_pdf(filepath):
    extracted_text = ""

    # Extract text using pdfplumber
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text
    except Exception as e:
        print(f"Error during text extraction with pdfplumber: {e}")

    return extracted_text

def initialize_chain(model_shorthand,system_prompt, history=False):

    output_parser = StrOutputParser()
    
    model_name = {
        'gpt':'gpt-4o-mini',
        'llama':'llama3-8b-8192',
        'opus':'claude-3-5-sonnet-20240620',
        '4o':'gpt-4o',
    }

    name = model_name[model_shorthand]

    model_farm = {
        'gpt':ChatOpenAI,
        'llama':ChatGroq,
        'opus':ChatAnthropic,
        '4o':ChatOpenAI
    }

    model = model_farm[model_shorthand](model=name)

    if history:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    system_prompt,
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human","{input}"),
            ]
        )
        base_chain = prompt | model | output_parser
        message_history = ChatMessageHistory()
        chain = RunnableWithMessageHistory(
            base_chain,
            lambda session_id: message_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    else:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    system_prompt
                ),
                (
                    "human",
                    "{input}"
                )
            ]
        )
        chain = prompt | model | output_parser

    return chain

# runs one turn of a conversation
def conversation_engine(chain, input):
    message = chain.invoke({"input":input},
                        {"configurable": {"session_id": "unused"}})
    return message

def process_transcript(text):
    # Find all dialogues
    dialogues = re.findall(r'<(.*?)>(.*?)</\1>', text, flags=re.DOTALL)
    results = [{'speaker':speaker, 'dialogue':dialogue} for speaker, dialogue in dialogues]
    return results

def format_script(script):
    # Replace <host> and <expert> tags with bold names
    script = re.sub(r'<host>(.*?)</host>', r'**alex:** \1', script)
    script = re.sub(r'<expert>(.*?)</expert>', r'**jamie:** \1', script)
    return script


def text_to_speech(message,filepath,cast):
    # Calling the text_to_speech conversion API with detailed parameters
    global eleven_client

    voices = {
        "host":cast['host'],
        "expert":cast['expert'] 
    }
    voice = voices[message["speaker"]]
    message = message["dialogue"]

    response = eleven_client.text_to_speech.convert(
        voice_id=voice,  # Adam pre-made voice
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=message,
        model_id="eleven_turbo_v2_5",  # use the turbo model for low latency, for other languages use the `eleven_multilingual_v2`
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=.75,
            style=0.0,
            use_speaker_boost=False,
        ),
    )

    # Writing the audio stream to the file
    with open(filepath, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)
    # Return the path of the saved audio file
    return filepath

def concatenate_audio(file_list, output_file, app_root):
    logging.info(f"Starting audio concatenation. Files to process: {len(file_list)}")
    
    combined = AudioSegment.empty()

    for file in file_list:
        if not os.path.exists(file):
            logging.warning(f"File not found: {file}")
            continue
        
        try:
            sound = AudioSegment.from_file(file)
            logging.info(f"Processed file: {file}, duration: {len(sound)}ms")
            combined += sound
        except Exception as e:
            logging.error(f"Error processing {file}: {str(e)}")
            continue

    logging.info(f"Combined audio duration: {len(combined)}ms")

    # Load the intro/outro file
    intro_outro_path = os.path.join(app_root, 'static', 'introoutro.wav')
    try:
        intro_outro = AudioSegment.from_file(intro_outro_path)
        logging.info(f"Intro/outro duration: {len(intro_outro)}ms")
    except Exception as e:
        logging.error(f"Error loading intro/outro: {str(e)}")
        intro_outro = AudioSegment.silent(duration=1000)  # 1 second of silence as fallback

    middle_options = ['middle1.wav','middle3.wav','middle4.wav']
    middle_path = os.path.join(app_root, 'static', random.choice(middle_options))
    try:
        middle = AudioSegment.from_file(middle_path)
        logging.info(f"Middle audio duration: {len(middle)}ms")
        middle = middle - 12  # Reduce volume
    except Exception as e:
        logging.error(f"Error loading middle audio: {str(e)}")
        middle = AudioSegment.silent(duration=1000)  # 1 second of silence as fallback

    fade_duration = min(8000, len(intro_outro) // 2, len(middle) // 2)  # Ensure fade duration isn't longer than half the audio
    logging.info(f"Fade duration: {fade_duration}ms")

    # Prepare intro/outro
    intro_outro = intro_outro.fade_out(duration=fade_duration)

    # Overlay intro at the beginning
    combined = combined.overlay(intro_outro, position=0)

    # Overlay outro at the end
    outro_position = max(0, len(combined) - len(intro_outro))
    combined = combined.overlay(intro_outro, position=outro_position)

    # Add middle if the podcast is longer than 4.5 minutes
    if len(combined) > 4.5 * 60 * 1000:
        middle = middle.fade_in(duration=fade_duration).fade_out(duration=fade_duration)
        middle_position = max(0, len(combined)//2 - 15000)
        combined = combined.overlay(middle, position=middle_position)

    logging.info(f"Final audio duration: {len(combined)}ms")

    # Export the final combined audio file
    try:
        combined.export(output_file, format="mp3")
        logging.info(f"Successfully exported to {output_file}")
    except Exception as e:
        logging.error(f"Error exporting audio: {str(e)}")
        raise

    # Clean up temporary files
    for file in file_list:
        try:
            os.remove(file)
        except Exception as e:
            logging.error(f"Error removing temporary file {file}: {str(e)}")

    return output_file

def create_podcast_from_script(podcast_script, temp_dir, static_dir, app_root):
    voices = {
        'host':["RPEIZnKMqlQiZyZd1Dae","H2gwnCCCGhjpKRQBynLT","WLKp2jV6nrS8aMkPPDRO","t7jjqLOG6kzCY6SckkfL"],
        'expert':["P7x743VjyZEOihNNygQ9","r27TA7xKV7nfUjudCBpS","ByLF4fg3sDo1TGXkjPMA", "t9IV45xnQb79w1JXFAIQ"]
    }
    cast = {"host":random.choice(voices['host']), "expert":random.choice(voices['expert'])}
    print(cast)
    podcast_name = f"podcast_{random.randint(0,1000)}.mp3"
    print("Processing podcast script")
    processed_script = process_transcript(podcast_script)
    print(processed_script[:5])
    file_list = []
    print(f"Creating podcast with {len(processed_script)} turns.")
    print("synthesizing audio files")
    
    with tempfile.TemporaryDirectory() as temp_audio_dir:
        for i, turn in enumerate(processed_script):
            print(f"synthesizing turn {i}")
            temp_file = os.path.join(temp_audio_dir, f"{turn['speaker']}_{i}.wav")
            file = text_to_speech(turn, temp_file, cast)
            file_list.append(file)

        output_file = os.path.join(static_dir, podcast_name)
        try:
            final_pod = concatenate_audio(file_list, output_file, app_root)
            print(f"Successfully created final podcast: {final_pod}")
        except Exception as e:
            print(f"Error during audio concatenation: {str(e)}")
            raise

    return final_pod

