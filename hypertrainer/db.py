from peewee import SqliteDatabase, Model, Field
import click
from flask import current_app, g
from flask.cli import with_appcontext


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


def get_db():
    if 'db' not in g:
        g.db = SqliteDatabase(current_app.config['DATABASE'])
        g.db.connect()

    return g.db


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
        database = get_db()


class EnumField(Field):
    def __init__(self, enum_type, **kwargs):
        super().__init__(**kwargs)

        self.enum_type = enum_type

    def db_value(self, value):
        return value.value

    def python_value(self, value):
        return self.enum_type(value)
