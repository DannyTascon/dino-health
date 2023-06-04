from flask import Flask, request, render_template
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from textblob import TextBlob
from firebase_admin import credentials, firestore, initialize_app
from werkzeug.exceptions import BadRequest
import openai
import json

from app.config import OPENAI_API_KEY, FIREBASE_CREDS_PATH, QUESTIONS_PATH

from flask import Blueprint, render_template

app = Blueprint('main', __name__)


# Define your form class
class SurveyForm(FlaskForm):
    response = StringField('Response:', validators=[DataRequired()])
    question1 = StringField('Question 1: How have you been feeling lately?', validators=[DataRequired()])
    question2 = StringField('Question 2: Rate your stress level on a scale of 1-10:', validators=[DataRequired()])
    question3 = StringField('Question 3: What are the major challenges you are facing right now?',
                            validators=[DataRequired()])
    submit = SubmitField('Submit')


# Check if the environment variables are set
if not OPENAI_API_KEY or not FIREBASE_CREDS_PATH or not QUESTIONS_PATH:
    raise ValueError("One or more environment variables are missing.")

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_CREDS_PATH)
initialize_app(cred)
db = firestore.client()

# Load questions from file
with open(QUESTIONS_PATH) as f:
    questions = json.load(f)


@app.route('/survey', methods=['GET', 'POST'])
def survey():
    form = SurveyForm()

    if form.validate_on_submit():
        answers = {f'question{i + 1}': form.data[f'question{i + 1}'] for i in range(len(questions))}
        assessment, feedback = generate_assessment_and_feedback(answers)
        survey_id = save_survey_data(answers, assessment, feedback)
        return render_template('feedback.html', assessment=assessment, feedback=feedback, survey_id=survey_id)

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
        "It seems like you're going through a tough time. Consider seeking professional help or reaching out to a " \
        "support network." if sentiment == 'negative' else \
            "Your responses indicate a neutral sentiment. Take some time to reflect on your feelings and consider " \
            "seeking support if needed."
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

            # Generate assessment for each response
            assessment_prompt = f"As a professional psychologist, based on the response: {response}"
            assessment_models = openai.Completion.create(
                engine="davinci",
                prompt=assessment_prompt,
                temperature=0.5,
                max_tokens=100,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )
            assessment = assessment_models.choices[0]['text'].strip()

            feedback.append({"question": question, "response": response, "assessment": assessment})
    else:
        feedback = [{"question": "No response provided.", "response": "", "assessment": "No assessment available."}]

    return feedback



def save_survey_data(answers, assessment, feedback):
    try:
        doc_ref = db.collection(u'surveys').document()
        doc_ref.set({
            'answers': answers,
            'assessment': assessment,
            'feedback': feedback
        })
        return doc_ref.id  # this is the new line of code
    except Exception as e:
        print(f"An error occurred while saving survey data: {e}")
        raise BadRequest("An error occurred while saving your survey. Please try again later.")

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

@app.route('/assessment/<survey_id>', methods=['GET'])
def assessment(survey_id):
    try:
        doc_ref = db.collection(u'surveys').document(survey_id)
        doc = doc_ref.get()
        if doc.exists:
            survey = doc.to_dict()
            return render_template('assessment.html', survey=survey)
        else:
            raise BadRequest("Survey not found.")
    except Exception as e:
        print(f"An error occurred while retrieving survey data: {e}")
        raise BadRequest("An error occurred while retrieving survey data.")

