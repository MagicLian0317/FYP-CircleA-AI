import os
import requests
from docx import Document
import PyPDF2
import json
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Get API key from environment variable
api_key = os.getenv("OPENAI_API_KEY")
base_url = "https://api.chatanywhere.tech/v1/chat/completions"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except Exception as e:
        print(f"Error reading text file: {e}")
        return ""

def read_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = [page.extract_text() for page in reader.pages if page.extract_text() is not None]
            return "\n".join(text).strip()
    except Exception as e:
        print(f"Error reading PDF file: {e}")
        return ""

def read_docx(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs if para.text]).strip()
    except Exception as e:
        print(f"Error reading DOCX file: {e}")
        return ""

def extract_resume_info(resume_text):
    if not api_key:
        return {"error": "API key not configured"}

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": f"Only return json format, Please extract the following information from the resume text:\nName, Gender, Phone, Email, Address, Education, Work Experience, Skills\n\n{resume_text}"
            }
        ],
        "max_tokens": 1000
    }

    try:
        response = requests.post(base_url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return json.loads(response_data['choices'][0]['message']['content'])
        else:
            return {"error": "Unexpected response structure"}
    except Exception as e:
        return {"error": str(e)}

def evaluate_resume(resume_text, job_title):
    if not api_key:
        return {"error": "API key not configured"}

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Please evaluate this resume for the role of a {job_title}. "
                    f"Provide a score out of 100 and format your response as follows:\n"
                    f"Score: [score]/100\n"
                    f"Details: [provide a brief evaluation].\n\n"
                    f"Resume: {resume_text}"
                )
            }
        ],
        "max_tokens": 300
    }

    try:
        response = requests.post(base_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return {"error": str(e)}

@app.route('/analyze', methods=['POST'])
def analyze_resume():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Read the file content based on its extension
        if filename.endswith('.txt'):
            resume_text = read_txt(filepath)
        elif filename.endswith('.pdf'):
            resume_text = read_pdf(filepath)
        elif filename.endswith('.docx'):
            resume_text = read_docx(filepath)

        # Clean up the temporary file
        os.remove(filepath)

        # Extract information
        info = extract_resume_info(resume_text)
        
        # If job_title is provided, also evaluate the resume
        job_title = request.form.get('job_title')
        if job_title:
            evaluation = evaluate_resume(resume_text, job_title)
            info['evaluation'] = evaluation

        return jsonify(info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port) 