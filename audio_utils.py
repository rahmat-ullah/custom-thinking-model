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

def speak_text(text, voice_id="alloy"): # Added voice_id parameter with default "alloy"
    """Converts the given text into speech using OpenAI Text-to-Speech with a selectable voice and plays it with Pygame."""
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
        
        print(f"Synthesizing speech with OpenAI TTS (voice: {voice_id}) for: \"{text}\"")
        response = client.audio.speech.create(
            model="tts-1",  # Standard model
            voice=voice_id,  # Use the voice_id parameter
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

    # Test 1: Basic TTS functionality (using default voice "alloy")
    print("\n--- Test 1: Basic OpenAI TTS (default voice 'alloy') ---")
    test_text_1 = "Hello, this is a test with the default alloy voice."
    print(f"Attempting to speak: \"{test_text_1}\"")
    speak_text(test_text_1) # Uses default voice

    # Test 1b: Different voice - "nova"
    print("\n--- Test 1b: OpenAI TTS with 'nova' voice ---")
    test_text_nova = "This is a test using the nova voice."
    print(f"Attempting to speak: \"{test_text_nova}\" with voice 'nova'")
    speak_text(test_text_nova, voice_id="nova")
    
    # Test 1c: Different voice - "shimmer"
    print("\n--- Test 1c: OpenAI TTS with 'shimmer' voice ---")
    test_text_shimmer = "And this is a test with the shimmer voice."
    print(f"Attempting to speak: \"{test_text_shimmer}\" with voice 'shimmer'")
    speak_text(test_text_shimmer, voice_id="shimmer")

    # Test 2: TTS with recognized speech (using a specific voice, e.g., "echo")
    print("\n--- Test 2: Speech Recognition and OpenAI TTS (voice 'echo') ---")
    print("Testing speech-to-text (listening for a few seconds)...")
    # Assuming listen_to_user remains functional and doesn't depend on TTS choice
    user_speech = listen_to_user() 
    
    if user_speech:
        print(f"Recognized speech: \"{user_speech}\"")
        tts_response = f"You said: {user_speech}"
        print(f"Attempting to speak with OpenAI TTS (voice 'echo'): \"{tts_response}\"")
        speak_text(tts_response, voice_id="echo") # Example: using 'echo' voice for response
    else:
        no_speech_message = "I could not understand what you said, or no audio was detected during the test."
        print(no_speech_message)
        speak_text(no_speech_message, voice_id="onyx") # Example: using 'onyx' for this message

    # Test 3: Handling of empty string (should not depend on voice_id)
    print("\n--- Test 3: Empty string input ---")
    speak_text("", voice_id="nova") # Voice_id is irrelevant here, but test it doesn't break

    # Test 4: Longer text (using default voice)
    print("\n--- Test 4: Longer text input with OpenAI TTS (default voice) ---")
    test_text_2 = "This is a slightly longer sentence for OpenAI Text to Speech to process, ensuring that playback handles it well using the default voice."
    print(f"Attempting to speak: \"{test_text_2}\"")
    speak_text(test_text_2) # Uses default "alloy"

    # Clean up pygame.mixer.
    if pygame.mixer.get_init():
        pygame.mixer.quit()
        print("\nPygame mixer quit.")
    
    print("\nAudio_utils (OpenAI TTS) test script finished.")
