from dotenv import load_dotenv
import os

load_dotenv()

# Load environment variables
openai_api_key = os.getenv('OPENAI_API_KEY')
firebase_creds_path = os.getenv('FIREBASE_CREDS_PATH')
questions_path = os.getenv('QUESTIONS_PATH')
SECRET_KEY = os.getenv('FLASK_WTF_PATH')

#rename to upper case