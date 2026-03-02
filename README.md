# GitHub Repository Summarizer API
**Personal ID:** 641463731438  
**Course:** AI Performance Engineering

## Overview
A high-performance API service that generates human-readable summaries of GitHub repositories. Built with FastAPI and integrated with Nebius LLM (Llama 3.1).

## Performance Features
* **Optimized Context**: Instead of reading all source code, the service analyzes the file tree and README to minimize token usage and latency.
* **Strict Timeouts**: LLM calls are capped at 10 seconds to ensure API responsiveness.
* **Token Management**: Response length is limited to 200 tokens to reduce inference cost and time.
* **Error Resilience**: Gracefully handles missing READMEs by falling back to repository structure analysis.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt