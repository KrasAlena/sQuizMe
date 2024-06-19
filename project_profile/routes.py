import os
import json
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
    quiz_text = quiz.text
    num_questions = quiz.num_questions

    questions, correct_answers = generate_questions_with_gpt(quiz_text, num_questions)


    # Save generated questions in db
    for i, question_text in enumerate(questions, start=1):
        question = Question(question_text=question_text, quiz_id=quiz.id)
        db.session.add(question)
        db.session.commit()

        for j, answer_text in enumerate(questions[question_text], start=1):
            is_correct = (j == correct_answers[i])
            answer = Answer(answer_text=answer_text, is_correct=is_correct, question_id=question.id)
            db.session.add(answer)
            db.session.commit()


def generate_questions_with_gpt(quiz_text, num_questions):
    # Create prompt for API ChatGPT
    prompt = f"analyze text below and generate {num_questions} quiz questions and strictly 4 answers for each (only one of them is correct). Use this structure:\n"
    prompt += "\t1. Question:\n\t1. answer\n\t2. answer\n\t3. answer\n\t4. answer\n"
    prompt += f"After the all questions give a dictionary of the correct answers like this:\n"
    prompt += "{1: 2, 2: 1, 3: 1, ...}, where key is the question number, value is a number of the correct answer.\n"

    # Add text to the prompt
    prompt += quiz_text

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
    generated_text = response['choices'][0]['message']['content'].strip()  # Получаем текст ответа
    generated_questions = {}
    correct_answers = {}

    current_question = None
    for line in generated_text.splitlines():
        line = line.strip()
        if line.endswith("Question:"):
            if current_question:
                correct_answers[len(generated_questions)] = correct_answer_index
                generated_questions[current_question] = answers
            current_question = line[:-1]
            answers = []
        elif current_question:
            if line.startswith("\t"):
                answers.append(line[1:].strip())
            elif line.startswith("{"):
                correct_answer_index = int(
                    line.split(": ")[1].split(",")[0].strip())

    if current_question and answers:
        correct_answers[len(generated_questions)] = correct_answer_index

        question = Question(question_text=current_question,
                            quiz_id=None)
        db.session.add(question)
        db.session.commit()


        for j, answer_text in enumerate(answers, start=1):
            is_correct = (j == correct_answer_index)
            answer = Answer(answer_text=answer_text, is_correct=is_correct, question_id=question.id)
            db.session.add(answer)
        db.session.commit()

    for question_text, answers in generated_questions.items():
        print(f"Question: {question_text}")
        for i, answer in enumerate(answers, start=1):
            print(f"{i}. {answer}")
        print()

    print("Correct answers:", correct_answers)

    return generated_questions, correct_answers


@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = quiz.questions

    return render_template('quiz.html', quiz=quiz, questions=questions)