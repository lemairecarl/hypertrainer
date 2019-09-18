cd hypertrainer
export FLASK_APP=../hypertrainer
flask init-db  # create tables if they don't exist
flask run