# NDA Reviewer

An AI-powered NDA review application that provides instant, consistent legal analysis based on learned patterns from 211+ NDAs.

## Overview

The NDA Reviewer uses Claude AI to analyze Non-Disclosure Agreements against a comprehensive Legal Review Playbook, providing:
- Instant classification of NDA terms and provisions
- Risk identification and flagging
- Consistent review criteria across all NDAs
- Structured analysis output in purple-highlighted Word documents

## Architecture

- **Backend**: FastAPI + SQLite, powered by Claude Opus 4.8 and Sonnet 4.6
- **Frontend**: React + TypeScript + Vite
- **AI**: Anthropic Claude API with Legal Review Playbook

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
echo "ANTHROPIC_API_KEY=your_key_here" > .env
echo "MODEL=claude-sonnet-4-6" >> .env
echo "HIGH_STAKES_MODEL=claude-opus-4-8" >> .env

# Start server
python -m uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Upload an NDA document (Word or PDF)
2. The system analyzes the document against the Legal Review Playbook
3. Review the highlighted output with color-coded analysis
4. Download the reviewed document

## Project Status

**Completed 2026-06-03**. Currently in live testing and stakeholder feedback phase.

## License

Proprietary - Ascential Intelligence
