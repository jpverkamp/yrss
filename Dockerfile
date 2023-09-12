FROM python:3.8
EXPOSE 5000
WORKDIR /app

RUN pip install poetry
ADD poetry.lock pyproject.toml .
RUN poetry install

ADD . .
CMD poetry run python yrss2.py