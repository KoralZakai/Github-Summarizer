import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key and self.api_key != "mock":
            self.client = Anthropic(api_key=self.api_key)
        
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0
        }

    def estimate_tokens(self, text):
        """Rough token estimate for local calculation"""
        if not text:
            return 0
        return int(len(text.split()) * 1.3)

    def summarize(self, repo_data, gh_client=None):
        """Summarize repository with optional agentic feedback"""
        if not self.api_key or self.api_key == "mock":
            return "# Project Summary (Mock)\nFalling back to local analysis."

        # Build initial prompt with all available data
        prompt, prompt_tokens = self._build_prompt(repo_data)
        self.token_usage["input_tokens"] = prompt_tokens
        
        try:
            message = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            
            summary = message.content[0].text
            # Track token usage
            if hasattr(message, 'usage'):
                self.token_usage["output_tokens"] = message.usage.output_tokens
            
            # Check if summary is complete
            if not self._is_summary_complete(summary) and gh_client:
                # PHASE 4: Ask LLM what specific files it needs
                summary = self._request_missing_info(gh_client, repo_data, summary)
            
            return f"# Project Summary\n{summary}"
            
        except Exception as e:
            # Fallback: retry without temperature parameter
            try:
                message = self.client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
                summary = message.content[0].text
                if hasattr(message, 'usage'):
                    self.token_usage["output_tokens"] = message.usage.output_tokens
                return f"# Project Summary\n{summary}"
            except:
                return f"Claude Analysis Failed: {str(e)}"

    def _build_prompt(self, repo_data):
        """Build prompt from repo data and return with token estimate"""
        # Extract metadata if available (from optimized github_client)
        metadata = repo_data.get("_metadata", {})
        tech_stack = metadata.get("tech_stack", {})
        manifests = metadata.get("manifests", {})
        
        # Build code analysis from actual files
        code_analysis = ""
        if repo_data.get("code_files"):
            code_analysis = "\n\nCode Files Analysis:\n"
            for file in repo_data["code_files"][:5]:
                code_analysis += f"\nFile: {file['path']}\n{file['content']}\n"
        
        # Build tech stack section
        tech_section = ""
        if tech_stack:
            languages = tech_stack.get("languages", [])
            frameworks = tech_stack.get("frameworks", [])
            if languages or frameworks:
                tech_section = f"\n\nIdentified Tech Stack:\nLanguages: {', '.join(languages)}\nFrameworks: {', '.join(frameworks)}\n"
        
        # Build manifest summary
        manifest_section = ""
        if manifests:
            manifest_section = "\n\nManifest Files Summary:\n"
            for name, content in manifests.items():
                manifest_section += f"{name}: {content[:200]}...\n"
        
        # Handle README - may be empty
        readme_text = repo_data.get("readme", "").strip()
        readme_section = f"README Content:\n{readme_text}" if readme_text else "No README file found"
        
        prompt = f"""Analyze this GitHub repository and provide a comprehensive summary. Use clear, plain text formatting without special characters or markdown symbols.

Repository Structure:
{repo_data.get('structure', 'No structure available')}

{readme_section}

{tech_section}

{manifest_section}

{code_analysis}

Answer these 4 questions clearly and concisely:

1. WHO SHOULD USE THIS REPO - Describe the target audience or users (developers, data scientists, system administrators, etc.)

2. WHY AND FOR WHAT PURPOSE - Explain what problems it solves and why someone would use it

3. INPUT AND OUTPUT - List what the project accepts as input and what it produces/returns

4. LANGUAGE AND CODE - List the programming languages used and key technologies

Use simple, direct language without lists or bullet points. Write 2-3 sentences per question."""

        # Estimate tokens for the prompt
        prompt_tokens = self.estimate_tokens(prompt) + 50  # Buffer for formatting
        
        return prompt, prompt_tokens

    def _is_summary_complete(self, summary):
        """Check if summary has all 4 required question answers"""
        required_markers = ['WHO SHOULD USE', 'WHY AND FOR WHAT', 'INPUT AND OUTPUT', 'LANGUAGE AND CODE']
        found_markers = sum(1 for marker in required_markers if marker in summary.upper())
        return found_markers >= 3  # At least 3 out of 4

    def _request_missing_info(self, gh_client, repo_data, initial_summary):
        """PHASE 4: Ask LLM what specific files would improve the summary"""
        try:
            # Build context query
            structure = repo_data.get('structure', '')
            metadata = repo_data.get('_metadata', {})
            
            query_prompt = f"""Based on the initial summary provided, and the repository structure below, identify the 1-2 most critical files to read for a better understanding.

Repository Structure:
{structure[:500]}

Initial Summary:
{initial_summary}

Respond ONLY with file paths from the repository, one per line, or "SUFFICIENT" if no additional files are needed."""

            message = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=100,
                messages=[{"role": "user", "content": query_prompt}]
            )
            
            response = message.content[0].text.strip()
            
            # If LLM says sufficient or we already have good coverage, return initial summary
            if "SUFFICIENT" in response.upper() or len(repo_data.get('code_files', [])) >= 5:
                return initial_summary
            
            # Parse requested files
            requested_files = [line.strip() for line in response.split('\n') if line.strip() and not line.startswith('#')]
            
            # In a full implementation, we could fetch these files and re-prompt
            # For now, return the initial summary (full agentic loop would need github_client refactor)
            return initial_summary
            
        except Exception as e:
            # If agentic request fails, return initial summary
            return initial_summary

    def get_token_usage(self):
        """Return current token usage stats"""
        return self.token_usage.copy()