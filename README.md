# 📄 Advanced PDF Editor, Redactor & Suite

A powerful, secure, multi-user web application built with **Streamlit** and **PyMuPDF (fitz)** that allows users to edit, redact, watermark, sign, merge, split, and secure PDF files directly from the browser. It also features a built-in user authentication system, role-based admin approval workflow via **Supabase** and **Resend**, and an interactive canvas for drawing signatures with a mouse or touchscreen.

---

## ✨ Features

1. **📄 Comprehensive PDF Operations & Editing**
   - **Page Management:** Rotate pages and delete unwanted pages.
   - **Text Redaction & Replacement:** Automatically find and blackout/erase sensitive text or dynamically replace it with custom placeholder text (e.g., `[REDACTED]`).
   - **Coordinate-Based Erasing:** Target and erase custom coordinate rectangles on any page.
   - **Digital Signatures:** Draw signatures directly on-screen using your mouse or touch device (via `streamlit-drawable-canvas`), or upload a custom signature PNG. Automatically strips white backgrounds for a clean transparent stamp.
   - **Watermarks & Borders:** Add customized semi-transparent text watermarks and page borders.
   - **OCR Support:** Optional Tesseract OCR fallback for scanned or image-based PDFs.
   - **Metadata & Security:** Scrub hidden author/date metadata and password-protect output PDFs with 256-bit AES encryption.

2. **🔀 Multi-File Management**
   - Merge multiple PDFs into a single unified document.
   - Split or extract specific pages from a PDF into a new standalone file.
   - Extract all embedded images from a PDF into a downloadable ZIP archive.

3. **🔐 Secure User Authentication & Approval Workflow**
   - User sign-up, login (hashed passwords using `bcrypt`), and session state management.
   - Admin approval queue: New users start in a `pending` state. Admins receive an email notification via **Resend** with secure 1-click approval or rejection links.

---

## 🛠️ Tech Stack

* **Frontend/UI:** [Streamlit](https://streamlit.io/)
* **PDF Processing:** [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)
* **Signature Canvas:** [streamlit-drawable-canvas](https://github.com/andfanilo/streamlit-drawable-canvas)
* **Database & Auth Storage:** [Supabase](https://supabase.com/)
* **Email Service:** [Resend](https://resend.com/)
* **Utilities:** `Pillow`, `numpy`, `bcrypt`, `pytesseract`

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
