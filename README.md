# Adobe-1A-2025

# 📘 Adobe Hackathon – Round 1A: Understand Your Document

## 🚀 Objective

Extract a *structured outline* from a raw PDF document, identifying:
- Document Title
- Hierarchical headings: H1, H2, H3
- Page number for each heading

The output should be a valid JSON file that captures the structure as shown in the example.

---

## 🛠️ Approach

Our solution uses a combination of:
- *PDF parsing tools* (like PyMuPDF / pdfplumber) for text extraction
- *Rule-based heuristics* (based on font size, style, and position) for detecting hierarchy
- *Text normalization* and *page-wise scanning* for accurate heading detection

We avoid reliance on font size alone and consider layout patterns for better generalization across PDFs.

---

## 🧠 Model/Library Used

- PyMuPDF (fitz) – fast and efficient PDF parsing
- re – for regular expressions
- json – for output structure

✅ No ML model >200MB is used.  
✅ Fully CPU-based and offline.

---

## 🐳 Docker Instructions

> Ensure your system has Docker installed.

### 🔧 Build the Docker Image

```bash
docker build --platform linux/amd64 -t pdf-outline-extractor:latest .