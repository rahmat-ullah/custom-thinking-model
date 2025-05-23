import speech_recognition as sr
# import pyttsx3 # No longer used
import io
# from google.cloud import texttospeech # No longer used, replaced by OpenAI TTS
from openai import OpenAI
import pygame
import os # For environment variables, if not handled by config
import config # To access OPENAI_API_KEY

def listen_to_user():
    """Captures audio from the microphone and converts it to text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:
        print("Recognizing...")
        query = r.recognize_google(audio, language='en-us')
        print(f"User said: {query}\n")
        return query
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
        return ""
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return ""
    except Exception as e:
        print(f"An unknown error occurred during speech recognition: {e}")
        return ""

def speak_text(text):
    """Converts the given text into speech using OpenAI Text-to-Speech and plays it with Pygame."""
    if not text:
        print("No text provided to speak.")
        return

    if not config.OPENAI_API_KEY:
        print("WARNING: OPENAI_API_KEY not found in config.")
        print("OpenAI TTS will fail. Falling back to print output.")
        print(f"Message to speak: {text}")
        return

    try:
        # Ensure pygame mixer is initialized
        if not pygame.mixer.get_init():
            print("Initializing pygame mixer...")
            pygame.mixer.init()

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        print(f"Synthesizing speech with OpenAI TTS for: \"{text}\"")
        response = client.audio.speech.create(
            model="tts-1",  # Standard model
            voice="alloy",  # Example voice
            input=text,
            response_format="mp3"
        )
        print("Speech synthesized successfully.")

        audio_fp = io.BytesIO(response.content)
        print("Loading audio to pygame mixer...")
        pygame.mixer.music.load(audio_fp)
        print("Playing audio...")
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        print("Audio playback finished.")

    except pygame.error as pg_err:
        print(f"Pygame error during TTS playback: {pg_err}")
        print("Falling back to basic print output for the message.")
        print(f"Message to speak: {text}")
    except Exception as e:
        print(f"An error occurred during OpenAI TTS or audio playback: {e}")
        print("Important: Ensure OPENAI_API_KEY is set correctly in config and you have internet access.")
        print("Falling back to basic print output for the message.")
        print(f"Message to speak: {text}")

if __name__ == '__main__':
    print("Starting audio_utils test script (with OpenAI TTS)...")
    
    # Initialize pygame.mixer once at the start of the script.
    try:
        pygame.mixer.init()
        print("Pygame mixer initialized successfully for test script.")
    except pygame.error as pg_err:
        print(f"Failed to initialize pygame.mixer for test script: {pg_err}. TTS playback will fail.")

    # Test 1: Basic TTS functionality
    print("\n--- Test 1: Basic OpenAI TTS ---")
    test_text_1 = "Hello, this is a test of the new OpenAI Text to Speech with Pygame."
    print(f"Attempting to speak: \"{test_text_1}\"")
    speak_text(test_text_1)

    # Test 2: TTS with recognized speech (if listen_to_user works independently)
    print("\n--- Test 2: Speech Recognition and OpenAI TTS ---")
    print("Testing speech-to-text (listening for a few seconds)...")
    # Assuming listen_to_user remains functional and doesn't depend on TTS choice
    user_speech = listen_to_user() 
    
    if user_speech:
        print(f"Recognized speech: \"{user_speech}\"")
        tts_response = f"You said: {user_speech}"
        print(f"Attempting to speak with OpenAI TTS: \"{tts_response}\"")
        speak_text(tts_response)
    else:
        no_speech_message = "I could not understand what you said, or no audio was detected during the test."
        print(no_speech_message)
        speak_text(no_speech_message)

    # Test 3: Handling of empty string
    print("\n--- Test 3: Empty string input ---")
    speak_text("") # Should print "No text provided to speak." and return.

    # Test 4: Longer text
    print("\n--- Test 4: Longer text input with OpenAI TTS ---")
    test_text_2 = "This is a slightly longer sentence for OpenAI TTS to process, ensuring that playback handles it well."
    print(f"Attempting to speak: \"{test_text_2}\"")
    speak_text(test_text_2)

    # Clean up pygame.mixer.
    if pygame.mixer.get_init():
        pygame.mixer.quit()
        print("\nPygame mixer quit.")
    
    print("\nAudio_utils (OpenAI TTS) test script finished.")
