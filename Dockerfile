# Use the official lightweight Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]