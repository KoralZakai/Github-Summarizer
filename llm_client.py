import os
from openai import OpenAI
import httpx

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("NEBIUS_API_KEY")
        self.base_url = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1")
        self.client = OpenAI(
            api_key=self.api_key if self.api_key != "mock" else "placeholder",
            base_url=self.base_url,
            http_client=httpx.Client(timeout=10.0)
        )

    def summarize(self, repo_data):
        if not self.api_key or self.api_key == "mock":
            return """
## Project Overview (Mock Mode)
This project appears to be a Python-based library.
### Key Tech Stack
* Python
* Pytest
### Summary
The repository structure suggests a focused tool for HTTP requests and API interactions.
            """

        prompt = f"""
        Repo Structure:
        {repo_data['structure']}
        
        README Content:
        {repo_data['readme'][:2000]}
        
        Summarize this GitHub repository for a developer. 
        Use Markdown with 'Overview', 'Tech Stack', and 'Key Features' sections.
        """

        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Meta-Llama-3.1-70B-Instruct",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Service unavailable: {str(e)}"