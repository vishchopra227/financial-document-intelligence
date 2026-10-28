# 📊 Financial Document Intelligence
### AI-Powered Financial Document Analysis using Retrieval-Augmented Generation (RAG)

**Turn complex financial documents into actionable insights.**

Financial Document Intelligence is an AI-powered application designed to help users interact with financial documents, retrieve relevant information, extract key financial metrics, and compare multiple documents through a conversational interface.

Built with **FastAPI, React, TypeScript, and Groq-powered LLM integration**, the project combines document processing, hybrid retrieval, and Retrieval-Augmented Generation (RAG) to make financial information easier to explore and understand.

---

## ✨ Key Features

### 📄 1. Financial Document Processing
- Upload and process supported financial documents.
- Extract text from documents for downstream analysis.
- Split document content into manageable chunks for retrieval.
- Preserve page-level attribution to help identify the source of retrieved information.

### 💬 2. AI-Powered Document Chat
- Ask natural-language questions about financial documents.
- Retrieve relevant context before generating answers.
- Use retrieved document content to support responses.
- Access information without manually searching through lengthy reports.

### 🔎 3. Hybrid Information Retrieval
The RAG pipeline combines multiple retrieval techniques:

- **BM25 retrieval:** Finds relevant content using lexical matching.
- **Cosine similarity:** Compares embedding vectors to identify similar content.
- **Reciprocal Rank Fusion (RRF):** Combines ranked retrieval results to improve the final selection of relevant chunks.

This approach helps balance exact keyword matching with similarity-based retrieval.

### 📑 4. Multi-Document Comparison
- Compare information across multiple documents.
- Retrieve relevant content for comparative analysis.
- Use the comparison workflow to examine differences between financial documents.

### 📈 5. Financial Metrics Extraction
- Extract selected financial metrics from document content.
- Organize extracted information for easier inspection.
- Support structured financial analysis using a dedicated metrics workflow.

*Metric extraction uses heuristic-based logic; results may require manual verification.*

### 📤 6. Data Export
- Export supported comparison or metrics results.
- Use CSV and JSON formats for further analysis and reporting.

### ⚙️ 7. Backend APIs
The FastAPI backend provides dedicated routes for:
- Chat
- Document management
- Health checks
- Settings
- Financial metrics
- Multi-document comparison

### 🧪 8. Testing
The project includes backend tests covering areas such as:
- Health endpoints
- Document operations
- RAG workflows
- Database behavior
- Comparison and metrics functionality

---

## 🏗️ System Architecture

```text
                 ┌──────────────────────────┐
                 │       User Interface     │
                 │      React + TypeScript  │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │       FastAPI Backend    │
                 │       REST API Layer     │
                 └────────────┬─────────────┘
                              │
                 ┌────────────▼─────────────┐
                 │   Document Ingestion     │
                 │   Parsing and Chunking   │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │    Retrieval Pipeline    │
                 │                          │
                 │  • BM25 Retrieval        │
                 │  • Cosine Similarity     │
                 │  • Reciprocal Rank Fusion│
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │     Relevant Context     │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │      LLM Integration     │
                 │       Groq API           │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │    Answer / Analysis     │
                 │   Comparison / Metrics   │
                 └──────────────────────────┘
```

*Conceptual architecture illustrating the main processing flow.*

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Frontend | React |
| Programming Language | TypeScript |
| Frontend Build Tool | Vite |
| Backend | Python, FastAPI |
| API Communication | REST APIs |
| Language Model Integration | Groq API |
| Retrieval | BM25, cosine similarity, Reciprocal Rank Fusion |
| Data Processing | Python-based document ingestion and metrics extraction |
| Database Layer | SQLAlchemy |
| Testing | Pytest |
| Configuration | Environment variables |

**Embedding note:** The current implementation uses deterministic local embeddings. These should not be confused with pretrained, production-grade semantic embedding models.

---

## 🔌 API Overview

The backend organizes its API functionality into separate route modules.

| Module | Responsibility |
|---|---|
| `chat.py` | Conversational document interaction |
| `documents.py` | Document-related operations |
| `compare.py` | Multi-document comparison |
| `metrics.py` | Financial metrics functionality |
| `health.py` | Application health checks |
| `settings.py` | Application settings |

For exact endpoint paths, request schemas, and response formats, inspect the FastAPI documentation at `/docs` while the backend is running.

---

## 🧠 How RAG Works in This Project

Retrieval-Augmented Generation connects document retrieval with language model generation.

### Step 1: Document Ingestion
The application processes supported documents and extracts their text.

### Step 2: Text Chunking
Extracted content is divided into smaller chunks. Page attribution helps retain information about where content originated.

### Step 3: Retrieval
The retrieval pipeline combines lexical search and embedding-based similarity.

### Step 4: Rank Fusion
Reciprocal Rank Fusion combines ranked results from different retrieval methods.

### Step 5: Context Preparation
Relevant chunks are selected and passed into the downstream processing workflow.

### Step 6: Response Generation
The language model generates a response using the supplied context and the application's configured prompt logic.

### Step 7: Financial Analysis
Dedicated workflows support multi-document comparison, selected metrics extraction, and structured data export.

---

## 🎯 Project Objective

The objective of Financial Document Intelligence is to explore how document processing, information retrieval, and large language models can work together to simplify financial document analysis.

The project demonstrates practical concepts in:

- Retrieval-Augmented Generation (RAG)
- Hybrid information retrieval
- Backend API development
- LLM integration
- Document processing
- Financial information extraction
- Multi-document analysis
- Full-stack application development

---

## 👨‍💻 Author

**Developed as an AI/ML and full-stack project.**

GitHub Repository:  
https://github.com/vishchopra227/financial-document-intelligence
