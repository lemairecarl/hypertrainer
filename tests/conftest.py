import os
import tempfile

import pytest
from hypertrainer import create_app
from hypertrainer.computeplatform import LocalPlatform
import hypertrainer.utils


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    output_dir = tempfile.TemporaryDirectory()
    os.environ['HYPERTRAINER_OUTPUT'] = output_dir.name
    os.environ['HYPERTRAINER_PATH'] = os.path.join(os.getcwd(), 'scripts')

    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
    })
    client = app.test_client()

    LocalPlatform.setup_output_path()
    hypertrainer.utils.setup_scripts_path()

    with app.app_context():
        from hypertrainer.db import init_db, init_app
        init_app(app)
        init_db()

    yield client

    os.close(db_fd)
    os.unlink(app.config['DATABASE'])
    output_dir.cleanup()
