from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign up')


class QuizForm(FlaskForm):
    quiz_name = StringField('Quiz Name', validators=[DataRequired(), Length(min=2, max=100)])
    quiz_text = TextAreaField('Quiz Text', validators=[DataRequired()])
    num_questions = SelectField('How many questions to generate', choices=[('10', '10'), ('15', '15'), ('20', '20')], default='10', validators=[DataRequired()])
    generate_button = SubmitField('Generate')


class AnswerForm(FlaskForm):
    submit = SubmitField('Finish')


def create_answer_form(num_questions):
    class DynamicAnswerForm(FlaskForm):
        pass

    for i in range(1, num_questions + 1):
        setattr(DynamicAnswerForm, f'answer_{i}',
                RadioField(f'Question {i} Answer', choices=[], coerce=int, validators=[DataRequired()]))

    setattr(DynamicAnswerForm, 'submit', SubmitField('Finish'))

    return DynamicAnswerForm()