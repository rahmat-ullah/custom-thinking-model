import speech_recognition as sr
import pyttsx3

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
    """Converts the given text into speech."""
    if not text:
        print("No text provided to speak.")
        return
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"An error occurred during text-to-speech: {e}")

if __name__ == '__main__':
    # Example usage (optional, for testing)
    print("Testing speech-to-text...")
    user_speech = listen_to_user()
    if user_speech:
        print(f"Recognized speech: {user_speech}")
        print("\nTesting text-to-speech...")
        speak_text(f"You said: {user_speech}")
    else:
        speak_text("I could not understand what you said.")
    
    speak_text("This is a test of the text to speech system.")
