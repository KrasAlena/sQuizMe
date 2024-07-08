from flask_login import current_user

def test_register(test_client):
    response = test_client.post('/register', data={
        'email': 'test@example.com',
        'name': 'Test User',
        'password': 'password',
        'confirm_password': 'password'
    }, follow_redirects=True)

    assert b'Your account has been created! You are now able to log in.' in response.data

    from project_profile.models import User
    with test_client.application.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        assert user is not None
        assert user.name == 'Test User'


def test_register_existing_email(test_client):
    response = test_client.post('/register', data={
        'email': 'test1@example.com',
        'name': 'Test User',
        'password': 'password',
        'confirm_password': 'password'
    }, follow_redirects=True)

    assert b'Your account has been created! You are now able to log in.' in response.data

    response = test_client.post('/register', data={
        'email': 'test1@example.com',
        'name': 'Another User',
        'password': 'password',
        'confirm_password': 'password'
    }, follow_redirects=True)

    assert b'Email address already registered. Please use a different email.' in response.data

    from project_profile.models import User
    with test_client.application.app_context():
        users_with_email = User.query.filter_by(email='test@example.com').all()
        assert len(users_with_email) == 1


def test_login(test_client):
    response = test_client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password'
    }, follow_redirects=True)

    assert b'Logged in successfully.' in response.data


def test_login_invalid_password(test_client):
    response = test_client.post('/login', data={
        'email': 'test@example.com',
        'password': 'wrong_password'
    }, follow_redirects=True)

    assert b'Login unsuccessful. Please check email and password.' in response.data


def test_logout(test_client):
    response = test_client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password'
    }, follow_redirects=True)

    assert b'Logged in successfully.' in response.data

    response = test_client.get('/logout', follow_redirects=True)

    assert b'You have been logged out.' in response.data

    with test_client.application.app_context():
        from flask_login import current_user
        assert not current_user.is_authenticated


def test_create_quiz(test_client):
    # Login as a test user (if necessary)
    test_client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password'
    })

    # Create a quiz
    with test_client.session_transaction() as session:
        # Get current user ID
        current_user_id = current_user.id

    response = test_client.post('/create_quiz', data={
        'quiz_name': 'Test Quiz',
        'quiz_text': 'This is a test quiz.',
        'num_questions': 10
    }, follow_redirects=True)

    assert b'Quiz created successfully!' in response.data

    # Check if the quiz is created in the database
    from project_profile.models import Quiz
    with test_client.application.app_context():
        quiz = Quiz.query.filter_by(name='Test Quiz').first()
        assert quiz is not None
        assert quiz.text == 'This is a test quiz.'
        assert quiz.num_questions == 10
        assert quiz.author_id == current_user_id  # Ensure the author ID is correct

    # Logout
    test_client.get('/logout')


def test_create_rename_share_delete_quiz(test_client):
    # Login as a test user
    test_client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password'
    })

    with test_client.session_transaction() as session:
        # Get current user ID
        current_user_id = current_user.id

    # Step 1: Create a quiz
    response = test_client.post('/create_quiz', data={
        'quiz_name': 'Test Quiz3',
        'quiz_text': 'This is a test quiz.',
        'num_questions': 10
    }, follow_redirects=True)

    assert b'Quiz created successfully!' in response.data

    # Check if the quiz is created in the database
    from project_profile.models import Quiz
    with test_client.application.app_context():
        quiz = Quiz.query.filter_by(name='Test Quiz3').first()
        assert quiz is not None
        assert quiz.text == 'This is a test quiz.'
        assert quiz.num_questions == 10
        assert quiz.author_id == current_user_id


    # Step 2: Rename the quiz
    response = test_client.post(f'/rename_quiz/{quiz.id}', data={
        'new_name': 'Updated Test Quiz3'
    }, follow_redirects=True)

    assert b'Quiz "Updated Test Quiz3" renamed successfully!' in response.data

    # Check if the quiz is renamed in the database
    with test_client.application.app_context():
        updated_quiz = Quiz.query.filter_by(id=quiz.id).first()
        assert updated_quiz.name == 'Updated Test Quiz3'

    # Step 3: Share the quiz
    response = test_client.post(f'/share_quiz/{quiz.id}', follow_redirects=True)

    assert b'Quiz shared successfully!' in response.data

    # Check if the quiz is shared in the database
    with test_client.application.app_context():
        shared_quiz = Quiz.query.filter_by(id=quiz.id).first()
        assert shared_quiz.is_public

    # Step 4: Delete the quiz
    response = test_client.post(f'/delete_quiz/{quiz.id}', follow_redirects=True)

    assert b'Quiz deleted successfully!' in response.data

    # Check if the quiz is deleted from the database
    with test_client.application.app_context():
        deleted_quiz = Quiz.query.filter_by(id=quiz.id).first()
        assert deleted_quiz is None

    # Logout
    test_client.get('/logout')