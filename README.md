# CiteVerify 🔍📄

**Automated AI Citation Verification for Scientific & Research Papers**  
*Built for SapthaHacks*

CiteVerify helps researchers, students, and reviewers verify whether citations in a scientific paper actually support the claims made in the text. Upload a PDF, and CiteVerify extracts claims, cross-checks original sources, and generates an interactive citation accuracy breakdown.

---

## ✨ Features

- **PDF Upload & Multi-Paper Support** — Drag and drop scientific papers and switch between multiple uploaded documents seamlessly.
- **Automated Claim & Source Verification** — Uses AI to extract cited claims and cross-check them against original source papers.
- **Citation Accuracy Dashboard** — Displays overall **Citation Accuracy**, **Scanned Sources**, and **Verified Claims** at a glance.
- **Downloadable Reports** — Generates structured Markdown and PDF verification reports (powered by ReportLab).

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React, Vite |
| **Backend** | Python, FastAPI, Uvicorn |
| **AI & Verification** | Google Gemini API |
| **Reporting** | ReportLab |
| **Deployment** | Vercel (Frontend), Render (Backend) |

---

## 📁 Project Structure

```text
citeverify/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point & routes
│   │   └── services/        # PDF parsing, verification & ReportLab generation
│   └── requirements.txt     # Python dependencies
└── frontend/
    ├── public/
    ├── src/                 # React + Vite UI components & API integration
    └── package.json
