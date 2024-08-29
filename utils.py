import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ChatMessageHistory
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
        'opus':'claude-3-5-sonnet-20240620'
    }

    name = model_name[model_shorthand]

    model_farm = {
        'gpt':ChatOpenAI,
        'llama':ChatGroq,
        'opus':ChatAnthropic
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



def text_to_speech(message,filepath):
    # Calling the text_to_speech conversion API with detailed parameters
    global eleven_client

    voices = {
        "host":"RPEIZnKMqlQiZyZd1Dae",
        "expert":"P7x743VjyZEOihNNygQ9" 
    }
    voice = voices[message["speaker"]]
    message = message["dialogue"]

    response = eleven_client.text_to_speech.convert(
        voice_id=voice,  # Adam pre-made voice
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=message,
        model_id="eleven_multilingual_v1",  # use the turbo model for low latency, for other languages use the `eleven_multilingual_v2`
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

from pydub import AudioSegment
import os

def concatenate_audio(file_list, output_file, app_root):
    # Initialize an empty AudioSegment
    combined = AudioSegment.empty()

    for file in file_list:
        # Load the audio file
        sound = AudioSegment.from_file(file)
        # Append it to the combined AudioSegment
        combined += sound

    # Load the intro/outro file
    intro_outro_path = os.path.join(app_root, 'static', 'introoutro.wav')
    intro_outro = AudioSegment.from_file(intro_outro_path)

    # Calculate fade duration (e.g., 3 seconds)
    fade_duration = 8000  # milliseconds

    # Prepare intro
    intro_outro = intro_outro.fade_out(duration=fade_duration)

    # Overlay intro at the beginning
    combined = combined.overlay(intro_outro, position=0)

    # Overlay outro at the end
    outro_position = len(combined) - len(intro_outro)
    combined = combined.overlay(intro_outro, position=outro_position)

    # Export the final combined audio file
    combined.export(output_file, format="mp3")

    # Clean up temporary files
    for file in file_list:
        os.remove(file)

    return output_file

def create_podcast_from_script(podcast_script, temp_dir, static_dir, app_root):
    podcast_name = f"podcast_{random.randint(0,1000)}.mp3"
    print("Processing podcast script")
    processed_script = process_transcript(podcast_script)
    print(processed_script[:5])
    file_list = []
    print(f"Creating podcast with {len(processed_script)} turns.")
    print("synthesizing audio files")
    for i, turn in enumerate(processed_script):
        print(f"synthesizing turn {i}")
        file = text_to_speech(turn, os.path.join(temp_dir, f"{turn['speaker']}_{i}.wav"))
        file_list.append(file)

    output_file = os.path.join(static_dir, podcast_name)
    final_pod = concatenate_audio(file_list, output_file, app_root)
    return final_pod

