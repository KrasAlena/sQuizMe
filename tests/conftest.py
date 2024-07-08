import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import pytest
from project_profile import app, db


@pytest.fixture(scope='module')
def test_client():

    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.test_client() as testing_client:
        with app.app_context():
            db.create_all()

        yield testing_client

        with app.app_context():
            db.session.remove()
            # db.drop_all()