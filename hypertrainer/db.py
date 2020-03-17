from peewee import SqliteDatabase, Model, Field

from hypertrainer.utils import yaml, yaml_to_str, hypertrainer_home

db_file = hypertrainer_home / 'db.sqlite'
database = SqliteDatabase(str(db_file))


def init_db():
    from hypertrainer.task import Task

    database.create_tables([Task])


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
