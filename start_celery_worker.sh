celery -A hypertrainer.celeryplatform worker --loglevel=info -Q jobs,$(hostname)
