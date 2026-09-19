## How to run?

which python

## Create venv
python -m venv .venv
source .venv/bin/activate

## Install dependencies
from examples/flask-app run:

pip install -r requirements.txt

## Run app
from examples/flask-app run:

python app.py

## Check status

open: http://127.0.0.1:5000/ and http://127.0.0.1:5000/health

excpected answer: status: ok