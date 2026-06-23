# 🤖 AI Agents & Intelligent Systems

## Overview
This repository contains a secure local Retrieval-Augmented Generation (RAG) agent project designed for on-device reasoning with private documents.

## Current Project
- `secure_rag_agent/` — a Streamlit-based RAG agent with local ChromaDB retrieval and Ollama-powered reasoning.

## Repository Structure
- `README.md` — top-level repository overview and usage guidance
- `.gitignore` — standard Python and local artifact exclusions
- `secure_rag_agent/` — main agent project
  - `main.py` — Streamlit entrypoint
  - `requirements.txt` — Python dependencies
  - `.env.example` — sample environment variables
  - `app/` — application modules
  - `data/` — local vector store location
  - `tests/` — unit tests

## Getting Started
1. Create a Python virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r secure_rag_agent/requirements.txt
   ```
2. Copy environment variables
   ```bash
   cp secure_rag_agent/.env.example secure_rag_agent/.env
   ```
3. Run the app
   ```bash
   streamlit run secure_rag_agent/main.py
   ```

## Notes
- Do not commit `.env` files or local vector stores.
- Keep `secure_rag_agent/data/` out of git for privacy and reproducibility.
- Use the project-specific `README.md` inside `secure_rag_agent/` for additional setup details.
