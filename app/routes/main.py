from flask import Flask, request, render_template
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from dotenv import load_dotenv
from textblob import TextBlob
from firebase_admin import credentials, firestore, initialize_app
from werkzeug.exceptions import BadRequest
import openai
import os
import json


# Define your form class
class SurveyForm(FlaskForm):
    response = StringField('Response:', validators=[DataRequired()])
    question1 = StringField('Question 1: How have you been feeling lately?', validators=[DataRequired()])
    question2 = StringField('Question 2: Rate your stress level on a scale of 1-10:', validators=[DataRequired()])
    question3 = StringField('Question 3: What are the major challenges you are facing right now?',
                            validators=[DataRequired()])
    submit = SubmitField('Submit')


load_dotenv()

# Load environment variables
openai_api_key = os.getenv('OPENAI_API_KEY')
firebase_creds_path = os.getenv('FIREBASE_CREDS_PATH')
questions_path = os.getenv('QUESTIONS_PATH')
SECRET_KEY = os.getenv('FLASK_WTF_PATH')

# Check if the environment variables are set
if not openai_api_key or not firebase_creds_path or not questions_path:
    raise ValueError("One or more environment variables are missing.")

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY

# Set OpenAI API key
openai.api_key = openai_api_key

# Initialize Firebase
cred = credentials.Certificate(firebase_creds_path)
initialize_app(cred)
db = firestore.client()

# Load questions from file
with open(questions_path) as f:
    questions = json.load(f)


@app.route('/survey', methods=['GET', 'POST'])
def survey():
    form = SurveyForm()

    if form.validate_on_submit():
        answers = {f'question{i + 1}': form.data[f'question{i + 1}'] for i in range(len(questions))}
        assessment, feedback = generate_assessment_and_feedback(answers)
        save_survey_data(answers, assessment, feedback)
        return render_template('feedback.html', assessment=assessment, feedback=feedback)

    # Retrieve the submitted surveys from the Firebase database
    survey_docs = db.collection(u'surveys').stream()
    surveys = [doc.to_dict() for doc in survey_docs]

    return render_template('survey.html', form=form, surveys=surveys)


def generate_ai_questions():
    class F(FlaskForm):
        pass

    for i, question in enumerate(questions, start=1):
        setattr(F, f'question{i}', StringField(question))
    setattr(F, 'submit', SubmitField('Submit'))

    return F()


def perform_sentiment_analysis(text):
    analysis = TextBlob(text)
    return 'positive' if analysis.sentiment.polarity > 0 else 'negative' if analysis.sentiment.polarity < 0 else 'neutral'


def generate_assessment_and_feedback(answers):
    sentiment = perform_sentiment_analysis(answers.get('response', ''))
    assessment = "You seem to be doing well. Keep up the positive mindset!" if sentiment == 'positive' else \
        "It seems like you're going through a tough time. Consider seeking professional help or reaching out to a support network." if sentiment == 'negative' else \
            "Your responses indicate a neutral sentiment. Take some time to reflect on your feelings and consider seeking support if needed."
    feedback = generate_feedback(answers)
    return assessment, feedback


def generate_feedback(answers):
    prompts = []
    for i, question in enumerate(questions):
        response = answers.get(f'question{i + 1}', '')
        if response:
            prompt = f"Question {i + 1}: {question}\nResponse: {response}"
            prompts.append(prompt)

    feedback = []
    if prompts:
        feedback_models = openai.Completion.create(
            engine="davinci",
            prompt=prompts,
            temperature=0.5,
            max_tokens=100,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            n=len(prompts)
        )
        for choice, prompt in zip(feedback_models.choices, prompts):
            text = choice['text'].strip()
            response_start = prompt.index("Response: ") + len("Response: ")
            question = prompt[:response_start]
            response = prompt[response_start:]
            feedback.append({"question": question, "response": response})
    else:
        feedback = [{"question": "No response provided.", "response": ""}]

    return feedback


def save_survey_data(answers, assessment, feedback):
    try:
        doc_ref = db.collection(u'surveys').document()
        doc_ref.set({
            'answers': answers,
            'assessment': assessment,
            'feedback': feedback
        })
    except Exception as e:
        print(f"An error occurred while saving survey data: {e}")
        raise BadRequest("An error occurred while saving your survey. Please try again later.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)


@app.route('/survey/<survey_id>', methods=['GET'])
def view_survey(survey_id):
    try:
        doc_ref = db.collection(u'surveys').document(survey_id)
        doc = doc_ref.get()
        if doc.exists:
            survey = doc.to_dict()
            return render_template('survey_details.html', survey=survey)
        else:
            raise BadRequest("Survey not found.")
    except Exception as e:
        print(f"An error occurred while retrieving survey data: {e}")
        raise BadRequest("An error occurred while retrieving survey data.")
