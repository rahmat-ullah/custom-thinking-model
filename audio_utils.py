import speech_recognition as sr
# import pyttsx3 # No longer used, replaced by Google Cloud TTS
import io
from google.cloud import texttospeech
import pygame
import os # For checking GOOGLE_APPLICATION_CREDENTIALS

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
    """Converts the given text into speech using Google Cloud Text-to-Speech and plays it with Pygame."""
    if not text:
        print("No text provided to speak.")
        return

    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        print("Google Cloud Text-to-Speech will likely fail. Falling back to print output.")
        print(f"Message to speak: {text}")
        return

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Wavenet-D"  # Example WaveNet voice (male)
            # Other options: "en-US-Wavenet-C" (female)
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        print(f"Synthesizing speech for: \"{text}\"")
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        print("Speech synthesized successfully.")

        # Use pygame to play the audio from memory
        # Initialize mixer if not already initialized.
        if not pygame.mixer.get_init():
            print("Initializing pygame mixer...")
            pygame.mixer.init()
        
        audio_fp = io.BytesIO(response.audio_content)
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
        print(f"An error occurred during Google Cloud TTS or playback: {e}")
        print("Important: Ensure GOOGLE_APPLICATION_CREDENTIALS is set correctly and you have internet access.")
        print("Falling back to basic print output for the message.")
        print(f"Message to speak: {text}")

if __name__ == '__main__':
    print("Starting audio_utils test script...")
    
    # It's good practice to initialize pygame.mixer once at the start of the script if testing multiple times.
    try:
        pygame.mixer.init()
        print("Pygame mixer initialized successfully for test script.")
    except pygame.error as pg_err:
        print(f"Failed to initialize pygame.mixer for test script: {pg_err}. TTS playback will fail.")
        # If pygame doesn't init, speak_text will print errors and fallback to text.

    # Test 1: Basic TTS functionality
    print("\n--- Test 1: Basic TTS ---")
    test_text_1 = "Hello, this is a test of the new Google Cloud Text to Speech with Pygame."
    print(f"Attempting to speak: \"{test_text_1}\"")
    speak_text(test_text_1)

    # Test 2: TTS with recognized speech
    print("\n--- Test 2: Speech Recognition and TTS ---")
    print("Testing speech-to-text (listening for a few seconds)...")
    user_speech = listen_to_user() # This function already prints "Listening..." and "Recognizing..."
    
    if user_speech:
        print(f"Recognized speech: \"{user_speech}\"")
        tts_response = f"You said: {user_speech}"
        print(f"Attempting to speak: \"{tts_response}\"")
        speak_text(tts_response)
    else:
        # listen_to_user() would have printed an error if recognition failed.
        no_speech_message = "I could not understand what you said, or no audio was detected during the test."
        print(no_speech_message) # Print to console as well for clarity
        speak_text(no_speech_message)

    # Test 3: Handling of empty string
    print("\n--- Test 3: Empty string input ---")
    speak_text("") # Should print "No text provided to speak." and return.

    # Test 4: Longer text (optional, to check for any issues with slightly larger audio)
    print("\n--- Test 4: Longer text input ---")
    test_text_2 = "This is a slightly longer sentence to ensure that playback and synthesis handle more content without issues. Pygame should stream this from memory efficiently."
    print(f"Attempting to speak: \"{test_text_2}\"")
    speak_text(test_text_2)

    # Clean up pygame.mixer if it was initialized by this test script.
    if pygame.mixer.get_init():
        pygame.mixer.quit()
        print("\nPygame mixer quit.")
    
    print("\nAudio_utils test script finished.")
