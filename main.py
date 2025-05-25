from typing import Optional

from fastapi import FastAPI, File, UploadFile

import re
import pdfplumber
import pytesseract

app = FastAPI()


def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_with_ocr(file):
    # OCR for all pages, returns concatenated text
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=300).original
            text += pytesseract.image_to_string(img) + "\n"
    return text

@app.post("/classify")
async def schedule_classify_task(file: Optional[UploadFile] = File(None)):
    if file is None:
        return {"error": "No file uploaded"}

    # Extract text using pdfplumber
    text = extract_text_from_pdf(file.file)
    #print('text', text)
    file.file.seek(0)  # Reset file pointer for OCR if needed

    # Heuristic classification
    doc_type = "OTHER"
    text_lower = text.lower()
    if "w-2" in text_lower and "wage and tax statement" in text_lower:
        doc_type = "W2"
    elif "form 1040" in text_lower:
        doc_type = "1040"
    elif "1099" in text_lower:
        doc_type = "1099"
    elif "1098" in text_lower:
        doc_type = "1098"
    elif any(x in text_lower for x in ["driver license", "passport", "identity card", "id card"]):
        doc_type = "ID Card"
    else:
        # Try OCR for handwritten note
        ocr_text = extract_text_with_ocr(file.file)
        ocr_text_lower = ocr_text.lower()
        #print('ocr_text', ocr_text_lower)
        # Try to detect if the OCR text contains common passport/ID identifiers
        if "nationality" in ocr_text_lower and "place of birth" in ocr_text_lower and "gender" in ocr_text_lower:
            doc_type = "ID Card"
        # criiteria: if OCR text is much longer than pdfplumber text, likely handwritten
        elif len(ocr_text.strip()) > len(text.strip()) * 1.5:
            doc_type = "Handwritten note"
        elif "handwritten" in ocr_text_lower or "note" in ocr_text_lower:
            doc_type = "Handwritten note"
        else:
            doc_type = "OTHER"

    # Extract year (tryingg both text and OCR text)
    year = None
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if not match:
        file.file.seek(0)
        ocr_text = extract_text_with_ocr(file.file)
        match = re.search(r"\b(19|20)\d{2}\b", ocr_text)
    if match:
        year = match.group(0)

    return {"document_type": doc_type, "year": year}
