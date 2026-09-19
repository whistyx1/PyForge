## How to run?

which python

## Create venv
python -m venv .venv
source .venv/bin/activate

## Install dependencies
from examples/fastapi-app run:

pip install -r requirements.txt

## Run app
from examples/flask-app run:from examples/fastapi-app run:
python -m uvicorn app:app --reload

## Check status

open: http://127.0.0.1:8000 and http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs


http://127.0.0.1:8000/docs - geerated automatically by fastapi even without /docs decorator


excpected answer: status: ok