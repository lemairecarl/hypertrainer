from peewee import SqliteDatabase, Model, Field
import click
from flask import g, current_app
from flask.cli import with_appcontext

from hypertrainer.utils import yaml, yaml_to_str


database = SqliteDatabase(None)


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    database.init(current_app.config['DATABASE'])

    @app.before_request
    def before_request():
        database.connect(reuse_if_open=True)

    @app.after_request
    def after_request(response):
        database.close()
        return response


def get_db():
    return database


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    from hypertrainer.task import Task

    db = get_db()
    db.create_tables([Task])


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


class BaseModel(Model):
    class Meta:
        database = database


class EnumField(Field):
    def __init__(self, enum_type, **kwargs):
        super().__init__(**kwargs)

        self.enum_type = enum_type

    def db_value(self, value):
        return value.value

    def python_value(self, value):
        return self.enum_type(value)


class YamlField(Field):
    def db_value(self, value):
        return yaml_to_str(value)

    def python_value(self, value):
        return yaml.load(value)
