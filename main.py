import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime

# Import your existing optimized logic
from github_client import GitHubClient
from llm_client import LLMClient
from run_summarizer import get_cached_summary, cache_summary

app = FastAPI(title="GitHub Repository Summarizer API")

# Initialize your clients
# Note: Ensure these classes handle their respective API keys from environment variables
github_client = GitHubClient()
llm_client = LLMClient()

# Define the request model based on Nebius requirements
class SummarizeRequest(BaseModel):
    github_url: str

# Define the response model based on Nebius requirements
class SummarizeResponse(BaseModel):
    summary: str
    technologies: List[str]
    structure: str

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "GitHub Repository Summarizer API",
        "version": "1.0",
        "endpoints": {
            "POST /summarize": "Summarize a GitHub repository",
            "GET /docs": "Interactive API documentation (Swagger UI)",
            "GET /redoc": "Alternative API documentation (ReDoc)"
        },
        "example": {
            "method": "POST",
            "url": "/summarize",
            "body": {"github_url": "https://github.com/owner/repo"}
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "GitHub Repository Summarizer"}

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """
    Endpoint to fetch GitHub repository data and return a structured summary.
    Includes optimizations like caching, selective tree fetching, and token filtering.
    """
    url = request.github_url.strip()
    
    # Validate URL format
    if not url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
    
    # 1. Check Cache Layer first (Performance Optimization)
    cached_summary, cached_metadata, access_count = get_cached_summary(url)
    if cached_summary:
        try:
            parsed_cache = json.loads(cached_summary)
            return SummarizeResponse(**parsed_cache)
        except (json.JSONDecodeError, ValueError):
            pass  # Cache corrupted, proceed with fresh fetch

    try:
        # 2. Fetch repository data from GitHub
        repo_data = github_client.get_repo_data(url)
        if not repo_data:
            raise HTTPException(status_code=404, detail="Repository not found or is private")
        
        # 3. Generate summary using LLM (streaming generator)
        summary_generator = llm_client.summarize(repo_data, github_client)
        final_summary_json = None
        for chunk in summary_generator:
            final_summary_json = chunk
        
        if not final_summary_json:
            raise HTTPException(status_code=500, detail="Failed to generate summary")
        
        # 4. Extract and validate JSON from response
        # LLM should return pure JSON, but handle cases where it might have extra whitespace
        final_summary_json = final_summary_json.strip()
        
        # Find JSON object boundaries in case of any extraneous text
        json_start = final_summary_json.find('{')
        json_end = final_summary_json.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            final_summary_json = final_summary_json[json_start:json_end]
        
        parsed_summary = json.loads(final_summary_json)
        
        # 5. Validate response contains required fields
        required_fields = {"summary", "technologies", "structure"}
        if not all(field in parsed_summary for field in required_fields):
            raise HTTPException(
                status_code=500, 
                detail=f"LLM response missing required fields. Required: {required_fields}"
            )
        
        # 6. Cache the result
        cache_summary(url, final_summary_json, {"fetched_at": str(datetime.now())})
        
        # 7. Return structured response
        return SummarizeResponse(**parsed_summary)
        
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON response from LLM")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid repository: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# To run this server: 
# uvicorn main:app --reload
# then open url - http://127.0.0.1:8000/docs for interactive API docs