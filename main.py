import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from github_client import GitHubClient
from llm_client import LLMClient

load_dotenv()

app = FastAPI()
gh_client = GitHubClient(token=os.getenv("GITHUB_TOKEN"))
llm_client = LLMClient()

class RepoRequest(BaseModel):
    repo_url: str

@app.post("/summarize")
async def summarize_repo(request: RepoRequest):
    try:
        repo_data = gh_client.get_repo_data(request.repo_url)
        summary = llm_client.summarize(repo_data)
        return {
            "status": "success",
            "personal_id": "641463731438",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)