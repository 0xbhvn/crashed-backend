FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the application code
COPY . .

# Run migrations and start the application with observer in headless mode
CMD python -m src migrate upgrade --revision head && python -m src monitor --skip-catchup --with-observer --headless 