# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import mimetypes
import os
import re
import struct
from google import genai
from google.genai import types
import tempfile
from pydub import AudioSegment
import logging
import random


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to: {file_name}")


def generate(text, app_root=None):
    """
    Generate a podcast-style audio file from the given text. Requires transcript to be in the following format:
    Speaker 1:
    [text]
    Speaker 2:
    [text]
    Speaker 1:
    [text]
    ...
    """
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-2.5-pro-preview-tts"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""Please read aloud the following in a podcast interview style:\n""" + text),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=[
            "audio",
        ],
        speech_config=types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    types.SpeakerVoiceConfig(
                        speaker="Speaker 1",
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Fenrir"
                            )
                        ),
                    ),
                    types.SpeakerVoiceConfig(
                        speaker="Speaker 2",
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Gacrux"
                            )
                        ),
                    ),
                ]
            ),
        ),
    )

    # Create a temporary directory for the audio files
    with tempfile.TemporaryDirectory() as temp_dir:
        file_list = []
        file_index = 0
        
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
            if chunk.candidates[0].content.parts[0].inline_data and chunk.candidates[0].content.parts[0].inline_data.data:
                file_name = os.path.join(temp_dir, f"audio_{file_index}")
                file_index += 1
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                data_buffer = inline_data.data
                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                if file_extension is None:
                    file_extension = ".wav"
                    data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)
                save_binary_file(f"{file_name}{file_extension}", data_buffer)
                file_list.append(f"{file_name}{file_extension}")
            else:
                print(chunk.text)

        # Combine all audio files
        combined = AudioSegment.empty()
        for file in file_list:
            if os.path.exists(file):
                try:
                    sound = AudioSegment.from_file(file)
                    combined += sound
                except Exception as e:
                    logging.error(f"Error processing {file}: {str(e)}")
                    continue

        # Add intro/outro music if app_root is provided
        if app_root:
            intro_outro_path = os.path.join(app_root, 'static', 'introoutro.wav')
            try:
                intro_outro = AudioSegment.from_file(intro_outro_path)
                intro_outro = intro_outro - 12  # Reduce volume
                fade_duration = len(intro_outro) // 2

                # Prepare intro/outro
                intro_outro = intro_outro.fade_out(duration=fade_duration)

                # Overlay intro at the beginning
                combined = combined.overlay(intro_outro, position=0)

                # Overlay outro at the end
                outro_position = max(0, len(combined) - len(intro_outro))
                combined = combined.overlay(intro_outro, position=outro_position)

                # Add middle music if the podcast is longer than 4.5 minutes
                if len(combined) > 4.5 * 60 * 1000:
                    middle_options = ['middle1.wav','middle4.wav']
                    middle_path = os.path.join(app_root, 'static', random.choice(middle_options))
                    try:
                        middle = AudioSegment.from_file(middle_path)
                        middle = middle - 12  # Reduce volume
                        middle = middle.fade_in(duration=fade_duration).fade_out(duration=fade_duration)
                        middle_position = max(0, len(combined)//2 - 15000)
                        combined = combined.overlay(middle, position=middle_position)
                    except Exception as e:
                        logging.error(f"Error loading middle audio: {str(e)}")

            except Exception as e:
                logging.error(f"Error loading intro/outro: {str(e)}")

        # Export the final combined audio file
        output_file = os.path.join(temp_dir, "final_podcast.mp3")
        try:
            combined.export(output_file, format="mp3")
            return output_file
        except Exception as e:
            logging.error(f"Error exporting audio: {str(e)}")
            raise

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Parses bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys. Values will be
        integers if found, otherwise None.
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts: # Skip the main type part
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                # Handle cases like "rate=" with no value or non-integer value
                pass # Keep rate as default
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass # Keep bits_per_sample as default if conversion fails

    return {"bits_per_sample": bits_per_sample, "rate": rate}


if __name__ == "__main__":
    generate()
