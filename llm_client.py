import os
import json
import requests
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator
import anthropic
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        # Priority: NEBIUS_API_KEY, fallback to ANTHROPIC_API_KEY
        nebius_key = os.getenv("NEBIUS_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        if nebius_key:
            self.api_key = nebius_key
            self.client = anthropic.Anthropic(
                api_key=nebius_key,
                base_url="https://api.nebius.ai/v1"  # Nebius endpoint
            )
        elif anthropic_key:
            self.api_key = anthropic_key
            self.client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            raise ValueError("Neither NEBIUS_API_KEY nor ANTHROPIC_API_KEY environment variable is set")
        
        self.model = "claude-haiku-4-5-20251001"
    
    def summarize(self, repo_data: dict, github_client) -> Generator[str, None, None]:
        """
        Generate a structured summary of a repository using Claude.
        Yields JSON strings that conform to the required schema.
        """
        # Build a comprehensive context from repo data
        repo_context = self._build_repo_context(repo_data, github_client)
        
        # Strict prompt enforcing JSON output with no filler
        prompt = f"""Analyze the following GitHub repository and respond with ONLY valid JSON (no additional text, no markdown, no code blocks).

Repository Context:
{repo_context}

Respond with exactly this JSON structure:
{{
    "summary": "A clear, concise human-readable description of what this project does and its main purpose",
    "technologies": ["list", "of", "main", "technologies", "frameworks", "and", "languages"],
    "structure": "A brief description of the repository layout and how the code is organized"
}}

Requirements:
- The "summary" must be informative and highlight the key functionality
- The "technologies" list should include programming languages, frameworks, and major dependencies
- The "structure" field should describe the project organization (e.g., "Modular structure with separate directories for models, utils, and tests")
- Return ONLY the JSON object, nothing else"""
        
        # Call Claude with streaming
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        ) as stream:
            accumulated_response = ""
            for text in stream.text_stream:
                accumulated_response += text
                yield accumulated_response
    
    def _build_repo_context(self, repo_data: dict, github_client) -> str:
        """Build comprehensive context from repository data"""
        context = f"""
Repository Name: {repo_data.get('name', 'Unknown')}
Description: {repo_data.get('description', 'No description provided')}
Language: {repo_data.get('language', 'Unknown')}
Stars: {repo_data.get('stargazers_count', 0)}
Forks: {repo_data.get('forks_count', 0)}

README Content:
{repo_data.get('readme', 'No README found')}

Directory Structure:
{json.dumps(repo_data.get('tree', {}), indent=2)}
"""
        return context