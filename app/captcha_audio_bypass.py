import asyncio
import re
from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
import uuid

load_dotenv()

class BypassAudioCaptcha:
    def __init__(self, audio_url: str):
        self.audio_url = audio_url
        self.audio_file_path = self.generate_random_filename("captcha_audio", "wav")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate_random_filename(self, base_name, extension):
        random_string = uuid.uuid4().hex[:8]  # Generate a random string of 8 characters
        return f"{base_name}_{random_string}.{extension}"

    async def run(self):
        self.download_audio()
        text = self.transcribe_audio()
        os.remove(self.audio_file_path)
        return text
    
    def download_audio(self):
        response = requests.get(self.audio_url)
        with open(self.audio_file_path, "wb") as audio_file:
            audio_file.write(response.content)
    
    def transcribe_audio(self):
        with open(self.audio_file_path, "rb") as audio_file:
            response = self.client.audio.translations.create(
                model="whisper-1",
                file=audio_file
            )
        text = response.text
        return re.sub(r'[^A-Za-z0-9 ]+', '', text)


if __name__ == "__main__":
    audio_url = "https://www.google.com/recaptcha/api2/payload?p=06AFcWeA4yzNr7tspCm3jQHpH5q3Z9jYe3SDhUhkedLe0fwRNEQj510atUFIfAbSNfNTeoB9YDIkmgOq93DZy5H3usom3Sa17Cg288fQsENqdV55YtH5gsubItXwokv79LTcxYqi0g3ShyXxO5rMbRg-OKxYxmZrVzmigJct2j1fGWtTeZa7wtxPQu1Myu4_rVyiy7qYg2Hky3VYc7lK_CQy1xwZkdrayR9Q&k=6Le3U_UpAAAAAGIErqsecSf4WhawaTucs7kvs2ni"
    captcha_bypass = BypassAudioCaptcha(audio_url)
    text = asyncio.run(captcha_bypass.run())
    print(text)
    