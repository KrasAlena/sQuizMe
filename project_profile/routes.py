import os
import json
import re
import ast
from flask import render_template, redirect, url_for, flash
from project_profile import app, db
from project_profile.models import User, Quiz, Question, Answer
from project_profile.forms import LoginForm, RegistrationForm, QuizForm
from flask_login import login_user, logout_user, current_user, login_required
import openai
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv('OPEN_AI')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.password == form.password.data:
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('create_quiz'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, name=form.name.data, password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    form = QuizForm()
    if form.validate_on_submit():
        quiz_name = form.quiz_name.data
        quiz_text = form.quiz_text.data
        num_questions = int(form.num_questions.data)

        new_quiz = Quiz(name=quiz_name, text=quiz_text, num_questions=num_questions, author=current_user)
        db.session.add(new_quiz)
        db.session.commit()

        flash('Quiz created successfully!', 'success')
        return redirect(url_for('generate_quiz', quiz_id=new_quiz.id))  # Передаем quiz_id

    return render_template('create_quiz.html', form=form)

@app.route('/generate_quiz/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def generate_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)

    if quiz.author != current_user:
        flash('You are not authorized to generate questions for this quiz.', 'danger')
        return redirect(url_for('index'))

    # Generate quiz questions
    generate_questions_for_quiz(quiz)

    flash('Questions generated successfully!', 'success')
    return redirect(url_for('quiz', quiz_id=quiz_id))


def generate_questions_for_quiz(quiz):
    questions, question_answer_dict = generate_questions_with_gpt(quiz, quiz.num_questions)

    # Save generated questions and answers in db
    for i, question_text in enumerate(questions, start=1):
        question = Question(question_text=question_text, quiz_id=quiz.id)
        db.session.add(question)
        db.session.commit()

        answers_for_question = question_answer_dict.get(str(i), [])

        for j, answer_text in enumerate(answers_for_question, start=1):
            is_correct = (j == 1)  # Assuming the first answer is always correct based on correct_answers structure
            answer = Answer(answer_text=answer_text, is_correct=is_correct, question_id=question.id)
            db.session.add(answer)

        db.session.commit()

    print("Questions and answers generated and saved successfully.")

def generate_questions_with_gpt(quiz, num_questions):
    # Create prompt for API ChatGPT
    prompt = f"analyze text below and generate {num_questions} quiz questions and strictly 4 answers for each (only one of them is correct). Use this structure:\n"
    prompt += "\t1. Question:\n\t1. answer\n\t2. answer\n\t3. answer\n\t4. answer\n"
    prompt += f"After the all questions give a dictionary of the correct answers like this:\n"
    prompt += "{{1: 2, 2: 1, 3: 1, ...}}, where key is the question number, value is a number of the correct answer.\n"

    # Add text to the prompt
    prompt += quiz.text

    # Call API ChatGPT
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=550,
        format="json"
    )

    # Testing
    print('JSON:')
    print(json.dumps(response, indent=2))
    print('Full response text:')
    print(response['choices'][0]['message']['content'])

    # Processing response
    generated_text = response['choices'][0]['message']['content']
    questions, question_answer_dict = parse_questions_and_answers(generated_text)

    # Prepare correct answers dictionary
    correct_answers_dict = {}
    for question_number_str, answers in question_answer_dict.items():
        question_number = int(question_number_str)
        correct_answers_dict[question_number] = [answers[correct_answers_dict.get(question_number, 1) - 1]]

    print("Questions and answers generated successfully.")

    return questions, question_answer_dict

def parse_questions_and_answers(generated_text):
    questions = []
    question_answer_dict = {}

    current_question_number = None
    current_answers = []

    lines = generated_text.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("{"):
            break  # Прекращаем обработку после того как найдем словарь с правильными ответами

        if re.match(r"^\d+\. Question:", line):
            if current_question_number is not None and current_answers:
                question_answer_dict[current_question_number] = current_answers
                current_answers = []

            # Извлекаем номер вопроса
            current_question_number = re.search(r'\d+', line).group()
            questions.append(line.split("Question: ")[1])
        elif re.match(r"^\d+\.", line):
            # Извлекаем вариант ответа
            answer_text = line.split(". ")[1]
            current_answers.append(answer_text)

    # Добавляем последний вопрос и его ответы в словарь
    if current_question_number is not None and current_answers:
        question_answer_dict[current_question_number] = current_answers

    return questions, question_answer_dict

@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = quiz.questions

    return render_template('quiz.html', quiz=quiz, questions=questions)