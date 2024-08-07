import os
import json
import re
import ast
from flask import request, render_template, redirect, url_for, flash
from flask_bcrypt import generate_password_hash, check_password_hash
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
        if user:
            if user.password.startswith('$2b$'):  # for hashed passwords
                if check_password_hash(user.password, form.password.data):
                    login_user(user)
                    flash('Logged in successfully.', 'success')
                    return redirect(url_for('create_quiz'))
                else:
                    flash('Login unsuccessful. Please check email and password.', 'danger')
            else:
                # for old users without hashed passwords
                if user.password == form.password.data:
                    login_user(user)
                    flash('Logged in successfully.', 'success')
                    return redirect(url_for('create_quiz'))
                else:
                    flash('Login unsuccessful. Please check email and password.', 'danger')
        else:
            flash('User not found.', 'danger')

    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email address already registered. Please use a different email.', 'danger')
        else:
            hashed_password = generate_password_hash(form.password.data).decode('utf-8')
            user = User(email=form.email.data, name=form.name.data, password=hashed_password)
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
    questions, question_answer_dict, correct_answers = generate_questions_with_gpt(quiz, quiz.num_questions)

    # Save generated questions and answers in db
    for i, question_text in enumerate(questions, start=1):
        question = Question(question_text=question_text, quiz_id=quiz.id)
        db.session.add(question)
        db.session.commit()

        answers_for_question = question_answer_dict.get(str(i), [])

        for j, answer_text in enumerate(answers_for_question, start=1):
            is_correct = (answer_text in correct_answers)
            answer = Answer(answer_text=answer_text, is_correct=is_correct, question_id=question.id)
            db.session.add(answer)

        db.session.commit()

    print("Questions and answers generated and saved successfully.")


def generate_questions_with_gpt(quiz, num_questions):
    """
        Generate quiz questions and answers using GPT-3 API based on the provided quiz text.

        Args:
            quiz (Quiz): The Quiz object containing quiz details.
            num_questions (int): Number of questions to generate.

        Returns:
            tuple: A tuple containing generated questions, question-answer dictionary, and correct answers.
    """
    prompt = f"""analyze the text below and generate {num_questions} quiz questions and strictly 4 answers for each (only one of them is correct). Use this structure:
    1. Question: [Your question here]
    1. [answer]
    2. [answer]
    3. [answer]
    4. [answer]

    2. Question: [Your question here]
    1. [answer]
    2. [answer]
    3. [answer]
    4. [answer]

    3. Question: [Your question here]
    1. [answer]
    2. [answer]
    3. [answer]
    4. [answer]

    ...

    {num_questions}. Question: [Your question here]
    1. [answer]
    2. [answer]
    3. [answer]
    4. [answer]

    After all questions, give a dictionary of the correct answers strictly like this ( STRICTLY without new lines between keys):
    {{1: 2, 2: 1, 3: 1, 4: 1, 5: 3, 6: 3, 7: 1, 8: 1, 9: 2, 10: 1}}
    """

    # Add text to the prompt
    prompt += quiz.text

    # Call API ChatGPT
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=1500,
        format="json"
    )

    # Testing
    print('JSON:')
    print(json.dumps(response, indent=2))
    print('Full response text:')
    print(response['choices'][0]['message']['content'])

    # Processing response
    generated_text = response['choices'][0]['message']['content']
    questions, question_answer_dict, correct_answers = parse_questions_and_answers(generated_text)


    print("Questions and answers generated successfully.")
    print(f'KEYS: {correct_answers}')
    return questions, question_answer_dict, correct_answers


def parse_questions_and_answers(generated_text):
    """
        Parses generated text to extract questions, answers, and correct answers.

        Args:
        - generated_text (str): Text containing questions, answers, and correct answers.

        Returns:
        - questions (list): List of parsed questions.
        - question_answer_dict (dict): Dictionary mapping question numbers to lists of answers.
        - correct_answers (list): List of correct answers.
    """
    questions = []
    question_answer_dict = {}
    correct_answers_dict = {}

    current_question_number = None
    current_answers = []

    lines = generated_text.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("{"):
            break

        if re.match(r"^\d+\. Question:", line):
            if current_question_number is not None and current_answers:
                question_answer_dict[current_question_number] = current_answers
                current_answers = []

            # Extract question number
            current_question_number = re.search(r'\d+', line).group()
            questions.append(line.split("Question: ")[1])
        elif re.match(r"^\d+\.", line):
            # Extract answer
            answer_text = line.split(". ")[1]
            current_answers.append(answer_text)

    # Add last question and its answers to the dictionary
    if current_question_number is not None and current_answers:
        question_answer_dict[current_question_number] = current_answers

    # match = re.search(r'\{(?:\n\d+: \d+,?)+\n\}', generated_text)
    match = re.search(r'\{\s*(\d+)\s*:\s*(\d+)\s*(,\s*(\d+)\s*:\s*(\d+)\s*)*\}', generated_text)

    if match:
        correct_answers_str = match.group()
        # Convert string to a dictionary using module ast
        try:
            correct_answers_dict = ast.literal_eval(correct_answers_str)
        except SyntaxError as e:
            print("Error during a string interpretation:", e)
    else:
        print("A string with the correct answers wasn't found")
    print(f'Correct answers: {correct_answers_dict}')

    correct_answers = []
    for question_number_str, correct_answer_index in correct_answers_dict.items():
        question_number = int(question_number_str)  # Convert key to integer
        try:
            correct_answer = question_answer_dict[str(question_number)][
                correct_answer_index - 1]  # -1 because correct_answer_index is 1-based
            correct_answers.append(correct_answer)
        except KeyError:
            print(f"Question {question_number} not found in the dictionary.")

    return questions, question_answer_dict, correct_answers


@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def quiz(quiz_id):
    """
        Display quiz questions and handle user answers for a given quiz.

        Args:
            quiz_id (int): The ID of the quiz to display.

        Returns:
            render_template: Renders the quiz template with quiz details and results.
    """
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = quiz.questions

    if request.method == 'POST':
        # Get answers from user
        correct_count = 0
        question_results = []

        for question in questions:
            correct_answer = next((answer for answer in question.answers if answer.is_correct), None)
            user_answer_id_str = request.form.get(f'answer{question.id}')

            # if user_answer_id == correct_answer.id:
            #     correct_count += 1
            if user_answer_id_str is None:
                # Handle the case where the answer is not provided
                user_answer_id = None
            else:
                user_answer_id = int(user_answer_id_str)

            if user_answer_id is not None and user_answer_id == correct_answer.id:
                correct_count += 1

            question_results.append({
                'question_text': question.question_text,
                'correct_answer': correct_answer.answer_text
            })

        # Preparing results to display
        results = {
            'correct_count': correct_count,
            'total_questions': len(questions),
            'question_results': question_results
        }

        return render_template('quiz.html', quiz=quiz, questions=questions, results=results)

    return render_template('quiz.html', quiz=quiz, questions=questions)


@app.route('/public_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def public_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = quiz.questions

    if request.method == 'POST':
        correct_count = 0
        question_results = []

        for question in questions:
            correct_answer = next((answer for answer in question.answers if answer.is_correct), None)
            user_answer_id = int(request.form.get(f'answer{question.id}'))

            if user_answer_id == correct_answer.id:
                correct_count += 1

            question_results.append({
                'question_text': question.question_text,
                'correct_answer': correct_answer.answer_text
            })

        results = {
            'correct_count': correct_count,
            'total_questions': len(questions),
            'question_results': question_results
        }

        return render_template('quiz.html', quiz=quiz, questions=questions, results=results)

    return render_template('quiz.html', quiz=quiz, questions=questions)


@app.route('/my_quizzes')
@login_required
def my_quizzes():
    quizzes = Quiz.query.filter_by(author=current_user).all()
    return render_template('my_quizzes.html', quizzes=quizzes)


@app.route('/rename_quiz/<int:quiz_id>', methods=['POST'])
@login_required
def rename_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)

    if quiz.author != current_user:
        flash('You are not authorized to rename this quiz.', 'danger')
        return redirect(url_for('my_quizzes'))

    new_name = request.form.get('new_name')
    if new_name:
        quiz.name = new_name
        db.session.commit()
        flash(f'Quiz "{quiz.name}" renamed successfully!', 'success')
    else:
        flash('Invalid new name provided.', 'danger')

    return redirect(url_for('my_quizzes'))


@app.route('/share_quiz/<int:quiz_id>', methods=['POST'])
@login_required
def share_quiz(quiz_id):
    """
        Share a quiz by marking it as public in the database.

        Args:
            quiz_id (int): The ID of the quiz to share.

        Returns:
            redirect: Redirects to the user's quizzes page after sharing the quiz.
    """
    quiz = Quiz.query.get_or_404(quiz_id)

    if quiz.author != current_user:
        flash('You are not authorized to share this quiz.', 'danger')
        return redirect(url_for('my_quizzes'))

    quiz.is_public = True
    db.session.commit()

    flash('Quiz shared successfully!', 'success')
    return redirect(url_for('my_quizzes'))


@app.route('/community_quizzes')
def community_quizzes():
    public_quizzes = Quiz.query.filter_by(is_public=True).all()
    return render_template('community_quizzes.html', public_quizzes=public_quizzes)


@app.route('/delete_quiz/<int:quiz_id>', methods=['POST'])
@login_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)

    if quiz.author != current_user:
        flash('You are not authorized to delete this quiz.', 'danger')
        return redirect(url_for('my_quizzes'))


    Question.query.filter_by(quiz_id=quiz.id).delete()
    db.session.delete(quiz)
    db.session.commit()

    flash('Quiz deleted successfully!', 'success')
    return redirect(url_for('my_quizzes'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))