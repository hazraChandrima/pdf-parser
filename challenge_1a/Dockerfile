# Adobe Hackathon Challenge 1a - PDF Processing Docker Container
FROM --platform=linux/amd64 python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PyMuPDF
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY process_pdfs.py .

# Create necessary directories
RUN mkdir -p /app/input /app/output

# Set Python path to include src directory
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Make the script executable
RUN chmod +x process_pdfs.py

# Run the PDF processing script
CMD ["python", "process_pdfs.py"]
