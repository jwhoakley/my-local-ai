# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Add any required OS pkgs
#RUN apt-get update && apt-get install -y \
#    curl \
#    vim-tiny \
#    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Streamlit app code
COPY . .

# Expose the default Streamlit port
EXPOSE 8501

# Run a quick healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Command to run the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
