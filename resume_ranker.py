
import os
from PyPDF2 import PdfReader

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text.lower()
    except:
        return ""

def rank_resumes(job_keywords, resume_folder='uploads'):
    scores = []
    for filename in os.listdir(resume_folder):
        if filename.endswith('.pdf'):
            filepath = os.path.join(resume_folder, filename)
            resume_text = extract_text_from_pdf(filepath)
            score = sum(1 for keyword in job_keywords if keyword.lower() in resume_text)
            scores.append((filename, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores
