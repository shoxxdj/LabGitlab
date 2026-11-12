FROM python:3.8
ADD . /app
WORKDIR /app
RUN pip install -r app/requirements.txt
ENV API_KEY=sk_live_FAKE_1234567890abcdef
EXPOSE 5000
CMD ["python", "app/app.py"]
