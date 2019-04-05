import os
import tempfile

import pytest
from hypertrainer import create_app


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    output_dir = tempfile.TemporaryDirectory()
    os.environ['HYPERTRAINER_OUTPUT'] = output_dir.name

    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
    })
    client = app.test_client()

    with app.app_context():
        from hypertrainer.db import init_db
        init_db()

    yield client

    os.close(db_fd)
    os.unlink(app.config['DATABASE'])
    output_dir.cleanup()
