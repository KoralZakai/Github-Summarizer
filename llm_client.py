import os
import json
import requests
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        """Generator that streams summary text chunks in real-time"""
        if not self.api_key or self.api_key == "mock":
            yield json.dumps({
                "summary": "Mock summary - Set a real API key in .env to get actual Claude analysis.",
                "technologies": [],
                "structure": "Mock mode enabled"
            })
            return

        prompt, prompt_tokens = self._build_prompt(repo_data)
        self.token_usage["input_tokens"] += prompt_tokens
        
        streamed_response = ""
        
        try:
            with self.client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    streamed_response += text
                
                final_message = stream.get_final_message()
                if hasattr(final_message, 'usage'):
                    self.token_usage["output_tokens"] += final_message.usage.output_tokens
            
            parsed_summary = self._parse_json_response(streamed_response)
            yield json.dumps(parsed_summary)
            
            if gh_client and not self._is_summary_complete(parsed_summary):
                refined = self._run_deep_dive_loop(gh_client, repo_data, parsed_summary)
                yield json.dumps(refined)
            
        except Exception as e:
            yield json.dumps({
                "summary": f"Claude Analysis Failed: {str(e)}",
                "technologies": [],
                "structure": "Error occurred"
            })

    def _parse_json_response(self, response_text):
        """Parse JSON response from Claude with error handling"""
        try:
            # Try to extract JSON from the response
            json_str = response_text.strip()
            
            # If response is wrapped in markdown code blocks, extract it
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            
            json_str = json_str.strip()
            parsed = json.loads(json_str)
            
            # Validate required fields
            if not isinstance(parsed, dict):
                raise ValueError("Response is not a JSON object")
            
            # Ensure required fields exist
            required_fields = {"summary", "technologies", "structure"}
            missing_fields = required_fields - set(parsed.keys())
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            
            return parsed
            
        except json.JSONDecodeError as e:
            return {
                "summary": "Failed to parse Claude response as JSON",
                "technologies": [],
                "structure": f"Parse error: {str(e)}"
            }

    def _run_deep_dive_loop(self, gh_client, repo_data, initial_summary):
        """Agentic Phase: Automatically identifies, fetches, and integrates missing technical details"""
        try:
            # Ask the LLM to identify the 2 most important missing files from the structure
            query_prompt = f"""Based on the current summary and the file structure below, identify the 2 most critical files to read for more technical depth.
            
            Repository Structure:
            {repo_data.get('structure', '')[:1000]}

            Current Summary:
            {initial_summary.get('summary', '')[:500]}...

            Respond ONLY with the full file paths, one per line. If no more files are needed, write 'SUFFICIENT'."""

            message = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": query_prompt}]
            )
            
            response = message.content[0].text.strip()
            if "SUFFICIENT" in response.upper():
                return initial_summary

            requested_paths = [line.strip() for line in response.split('\n') if line.strip()]
            additional_context = ""
            
            # Concurrent file fetching: Fetch all requested files in parallel using ThreadPoolExecutor
            def fetch_file_content(path):
                """Helper function to fetch a single file from GitHub API"""
                file_obj = next((f for f in repo_data.get('tree_data', []) if f.get('path') == path), None)
                if file_obj and "url" in file_obj:
                    try:
                        res = requests.get(file_obj["url"], headers=gh_client.headers, timeout=5)
                        if res.status_code == 200:
                            content = base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
                            return path, content[:2000]
                    except Exception:
                        pass
                return None
            
            # Use ThreadPoolExecutor to fetch all files concurrently (max 5 workers)
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_path = {executor.submit(fetch_file_content, path): path for path in requested_paths}
                
                # Collect results as they complete (not necessarily in order)
                for future in as_completed(future_to_path):
                    result = future.result()
                    if result:
                        path, content = result
                        additional_context += f"\n--- Deep-Dive File: {path} ---\n{content}\n"

            if not additional_context:
                return initial_summary

            # Second LLM call to integrate the new information into the final summary
            refine_prompt = f"""Refine the following summary using the additional file content provided. Output ONLY a valid JSON object with these exact fields:
            
            {{"summary": "high-level overview", "technologies": ["list", "of", "techs"], "structure": "directory explanation"}}
            
            Initial Summary:
            {json.dumps(initial_summary)}

            New Deep-Dive Content:
            {additional_context}
            
            Provide a more detailed and accurate analysis based on this new data. Return ONLY the JSON object, no other text."""
            
            final_message = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                messages=[{"role": "user", "content": refine_prompt}]
            )
            
            # Update token tracking for the refinement call
            if hasattr(final_message, 'usage'):
                self.token_usage["input_tokens"] += self.estimate_tokens(refine_prompt)
                self.token_usage["output_tokens"] += final_message.usage.output_tokens

            refined_text = final_message.content[0].text
            return self._parse_json_response(refined_text)

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
        
        prompt = f"""Analyze this GitHub repository and respond with ONLY a valid JSON object. Do not include any conversational filler, markdown formatting, or explanatory text.

        Repository Data:
        README Content: {repo_data.get('readme', 'No README available')}
        Structure: {repo_data.get('structure', '')[:1000]}
        Tech Stack: {tech_info}
        Code Samples: {code_samples}

        Return a JSON object with exactly these fields (no other text):
        {{
          "summary": "A high-level overview of the project's purpose and what it does",
          "technologies": ["list", "of", "languages", "frameworks", "and", "libraries"],
          "structure": "A concise explanation of the directory layout and key files"
        }}"""

        return prompt, self.estimate_tokens(prompt) + 150

    def _is_summary_complete(self, summary_dict):
        """Verify if summary dictionary has all required fields with content"""
        if not isinstance(summary_dict, dict):
            return False
        
        required_fields = {"summary", "technologies", "structure"}
        has_fields = required_fields.issubset(set(summary_dict.keys()))
        
        has_content = (
            summary_dict.get("summary") and len(str(summary_dict.get("summary", ""))) > 10 and
            summary_dict.get("structure") and len(str(summary_dict.get("structure", ""))) > 10
        )
        
        return has_fields and has_content

    def get_token_usage(self):
        """Return the accumulated token usage for cost calculation"""
        return self.token_usage.copy()