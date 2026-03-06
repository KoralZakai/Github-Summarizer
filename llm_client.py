import os
import json
import requests
import base64
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        # Initialize API key and client from environment
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key and self.api_key != "mock":
            self.client = Anthropic(api_key=self.api_key)
        
        # Track token usage across multiple calls
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0
        }

    def estimate_tokens(self, text):
        """Estimate token count based on word frequency (~1.3 tokens per word)"""
        if not text:
            return 0
        return int(len(str(text).split()) * 1.3)

    def summarize(self, repo_data, gh_client=None):
        """Main entry point for summarization with Mock support and Agentic Loop"""
        # Support for Mock mode to save API costs during testing
        if not self.api_key or self.api_key == "mock":
            return "# Project Summary (Mock)\nThis is a mock summary. Set a real API key in .env to get actual Claude analysis."

        # PHASE 1: Build the initial prompt and estimate input tokens
        prompt, prompt_tokens = self._build_prompt(repo_data)
        self.token_usage["input_tokens"] += prompt_tokens
        
        try:
            # PHASE 2-3: First call to Claude for initial analysis
            message = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1500,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            
            summary = message.content[0].text
            if hasattr(message, 'usage'):
                self.token_usage["output_tokens"] += message.usage.output_tokens
            
            # PHASE 4: Agentic Loop - If summary is incomplete, fetch more files and refine
            if gh_client and not self._is_summary_complete(summary):
                summary = self._run_deep_dive_loop(gh_client, repo_data, summary)
            
            return f"# Project Summary\n{summary}"
            
        except Exception as e:
            return f"Claude Analysis Failed: {str(e)}"

    def _run_deep_dive_loop(self, gh_client, repo_data, initial_summary):
        """Agentic Phase: Automatically identifies, fetches, and integrates missing technical details"""
        try:
            # Ask the LLM to identify the 2 most important missing files from the structure
            query_prompt = f"""Based on the current summary and the file structure below, identify the 2 most critical files to read for more technical depth.
            
            Repository Structure:
            {repo_data.get('structure', '')[:1000]}

            Current Summary:
            {initial_summary[:500]}...

            Respond ONLY with the full file paths, one per line. If no more files are needed, write 'SUFFICIENT'."""

            message = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=100,
                messages=[{"role": "user", "content": query_prompt}]
            )
            
            response = message.content[0].text.strip()
            if "SUFFICIENT" in response.upper():
                return initial_summary

            requested_paths = [line.strip() for line in response.split('\n') if line.strip()]
            additional_context = ""
            
            # Actually fetch the contents of the requested files from GitHub
            for path in requested_paths:
                file_obj = next((f for f in repo_data.get('tree_data', []) if f.get('path') == path), None)
                if file_obj and "url" in file_obj:
                    res = requests.get(file_obj["url"], headers=gh_client.headers, timeout=5)
                    if res.status_code == 200:
                        content = base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
                        # Add file content (truncated to 2000 chars) to the context
                        additional_context += f"\n--- Deep-Dive File: {path} ---\n{content[:2000]}\n"

            if not additional_context:
                return initial_summary

            # Second LLM call to integrate the new information into the final summary
            refine_prompt = f"""Refine the following summary using the additional file content provided.
            
            Initial Summary:
            {initial_summary}

            New Deep-Dive Content:
            {additional_context}
            
            Provide a more detailed and accurate 5-question analysis based on this new data."""
            
            final_message = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1500,
                messages=[{"role": "user", "content": refine_prompt}]
            )
            
            # Update token tracking for the refinement call
            if hasattr(final_message, 'usage'):
                self.token_usage["input_tokens"] += self.estimate_tokens(refine_prompt)
                self.token_usage["output_tokens"] += final_message.usage.output_tokens

            return final_message.content[0].text

        except Exception:
            # If the deep-dive fails, fallback to the initial summary
            return initial_summary

    def _build_prompt(self, repo_data):
        """Construct the initial prompt with README, structure, and tech stack"""
        metadata = repo_data.get("_metadata", {})
        tech_stack = metadata.get("tech_stack", {})
        
        # Build tech stack and code analysis strings
        tech_info = f"Languages: {', '.join(tech_stack.get('languages', []))}"
        code_samples = ""
        if repo_data.get("code_files"):
            for file in repo_data["code_files"][:3]:
                code_samples += f"\nFile: {file['path']}\n{file['content']}\n"
        
        prompt = f"""Analyze this GitHub repository as an expert.
        
        README Content:
        {repo_data.get('readme', 'No README available')}
        
        Structure:
        {repo_data.get('structure', '')[:1000]}
        
        Tech Stack:
        {tech_info}
        
        Code Samples:
        {code_samples}
        
        Answer these 5 questions comprehensively:
        1. WHO SHOULD USE THIS
        2. WHY AND PURPOSE
        3. INPUT AND OUTPUT
        4. LANGUAGE AND TECH
        5. KEY FEATURES AND CAPABILITIES"""

        return prompt, self.estimate_tokens(prompt) + 150

    def _is_summary_complete(self, summary):
        """Verify if all required sections are present in the response"""
        markers = ['WHO SHOULD', 'WHY AND', 'INPUT AND', 'LANGUAGE AND', 'KEY FEATURES']
        return sum(1 for m in markers if m in summary.upper()) >= 4

    def get_token_usage(self):
        """Return the accumulated token usage for cost calculation"""
        return self.token_usage.copy()