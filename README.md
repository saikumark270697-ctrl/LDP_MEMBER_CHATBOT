---
title: Liberty Dental Plan AI Chatbot
emoji: 🦷
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.31.0
app_file: app.py
pinned: false
---

# Liberty Dental Plan — AI Chatbot

An AI-powered chatbot for the Liberty Dental Plan public website.  
Answers questions about plans, providers, members, and brokers using content from Contentful CMS.

## How it works

```
Contentful CMS  →  data_pipeline.py  →  Pinecone (vectors)
                                              ↓
User question  →  Sentence Transformer  →  Pinecone search  →  Llama 3.3 70B  →  Answer
```

- **Knowledge base**: 496 documents from Contentful (sections, FAQs, pages, cards)
- **Embedding model**: `all-MiniLM-L6-v2` (sentence-transformers)
- **Vector store**: Pinecone (`liberty-dental-kb` index)
- **LLM**: Llama 3.3 70B via Groq (Gemini 2.5 Flash as fallback)
- **UI**: Streamlit

---

## Run locally

### 1. Prerequisites

- Python 3.11
- API keys for: Groq, Pinecone, Contentful, Gemini

### 2. Setup

```powershell
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment variables

Create a `.env` file in the project root:

```
CONTENTFUL_SPACE_ID=your_space_id
CONTENTFUL_ACCESS_TOKEN=your_access_token
ENVIRONMENT=your_environment
GROQ_API_KEY=your_groq_key
PINECONE_API_KEY=your_pinecone_key
GEMINI_API_KEY=your_gemini_key
```

### 4. Start the chatbot

```powershell
streamlit run app.py
```

Open your browser at: **http://localhost:8501**

### 5. Open the widget demo

Open `chatbot-widget-demo.html` directly in your browser (double-click the file).  
The floating chat icon will appear bottom-left. Click it to open the chatbot panel.

> **Note:** Streamlit must be running (`streamlit run app.py`) before opening the widget demo, otherwise the panel will show a loading spinner.

---

## Rebuild the knowledge base

Run this once to re-index all Contentful content into Pinecone:

```powershell
python data_pipeline.py
```

---

## Deploy to Hugging Face Spaces

1. Go to **huggingface.co** → New Space
2. Name it, select **Streamlit** SDK, choose **CPU Basic** (free)
3. Set **Repository secrets** (Settings → Repository secrets):

| Secret | Value |
|--------|-------|
| `CONTENTFUL_SPACE_ID` | your space id |
| `CONTENTFUL_ACCESS_TOKEN` | your token |
| `ENVIRONMENT` | your environment |
| `GROQ_API_KEY` | your groq key |
| `PINECONE_API_KEY` | your pinecone key |
| `GEMINI_API_KEY` | your gemini key |

4. Push this repo to the HF Space git remote:

```bash
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/liberty-dental-chatbot
git push hf main
```

---

## Deploy to Azure

See the GitHub Actions workflow at `.github/workflows/azure-deploy.yml`.

**Required GitHub Secrets:**

| Secret | Description |
|--------|-------------|
| `AZURE_WEBAPP_NAME` | Your Azure Web App name |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | XML from Azure Portal → Get publish profile |

**Azure App Service settings:**

- Runtime: Python 3.11 (Linux)
- Startup command: `bash startup.sh`
- `WEBSITES_PORT` = `8000`
- Add all `.env` keys as Application Settings

---

## Project structure

```
app.py                          — Main Streamlit chatbot application
data_pipeline.py                — Fetches Contentful content → Pinecone index
startup.sh                      — Azure App Service startup command
Procfile                        — Railway deployment start command
requirements.txt                — Python dependencies
Dockerfile                      — Docker container (alternative deploy)
.streamlit/config.toml          — Streamlit server config (headless, CORS off)
.github/workflows/
  azure-deploy.yml              — GitHub Actions CI/CD to Azure
chatbot-widget-demo.html        — LDP website with floating chat widget demo
ldp-how-it-works.html           — System architecture diagram
ldp-chatbot-guide.html          — Routing logic and link reference
ldp-counts.html                 — Contentful content coverage audit
ldp-contentful-suggestion.html  — CMS strategy guide
```
