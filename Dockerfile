FROM python:3.8
EXPOSE 5000
WORKDIR /app

ADD requirements.txt .
RUN pip3 install -r requirements.txt

ADD . .
CMD python3 yrss2.py