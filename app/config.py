from dotenv import load_dotenv
import os

load_dotenv()

# Load environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
FIREBASE_CREDS_PATH = os.getenv('FIREBASE_CREDS_PATH')
QUESTIONS_PATH = os.getenv('QUESTIONS_PATH')
SECRET_KEY = os.getenv('FLASK_WTF_PATH')

