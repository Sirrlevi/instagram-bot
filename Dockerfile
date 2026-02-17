FROM python:3.11-slim

WORKDIR /app

# Pehle instagrapi install karo (uski specific pydantic ke saath)
RUN pip install --no-cache-deps instagrapi==1.14.0

# Phir baaki dependencies install karo (groq apni pydantic lega, conflict hoga but Docker handle karega)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
