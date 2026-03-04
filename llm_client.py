import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

def select_model(repo_data):
    """Select optimal model based on repository complexity"""
    code_file_count = len(repo_data.get("code_files", []))
    repo_size = len(str(repo_data))
    
    # Simple repos: use Haiku (cost-effective)
    if code_file_count < 10 and repo_size < 50000:
        return "claude-haiku-4-5"
    
    # Medium repos: consider Sonnet for better accuracy
    elif code_file_count < 50 and repo_size < 200000:
        return "claude-sonnet-4-20250514"
    
    # Complex repos: Opus for multi-language analysis
    else:
        return "claude-opus-4-1-20250805"

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key and self.api_key != "mock":
            self.client = Anthropic(api_key=self.api_key)
        
        # System prompt for caching (rarely changes)
        self.system_prompt = """You are a GitHub repository analyzer. Provide concise, accurate summaries of projects. Focus on practical utility. Answer all 4 questions directly without preamble."""

    def summarize(self, repo_data):
        if not self.api_key or self.api_key == "mock":
            return "# Project Summary (Mock)\nFalling back to local analysis."

        # Build optimized code analysis (only essential files)
        code_analysis = ""
        if repo_data.get("code_files"):
            code_analysis = "Key Files Analyzed:\n"
            for file in repo_data["code_files"][:4]:
                code_analysis += f"{file['path']}: {file['content'][:150]}...\n"
        
        # Handle README - may be empty
        readme_text = repo_data.get("readme", "").strip()
        readme_section = f"README: {readme_text[:500]}" if readme_text else "No README found"
        
        # Optimized prompt with structured output format
        user_prompt = f"""Repository Structure (first files):
{repo_data.get('structure', 'N/A')}

{readme_section}

{code_analysis}

Answer these 4 questions (1-2 sentences each):
Q1: Who should use this repo (target users)?
Q2: Why and for what purpose (what problem does it solve)?
Q3: Input and output (what does it accept and produce)?
Q4: Languages and tech stack used?

Format: Q1: [answer]\nQ2: [answer]\nQ3: [answer]\nQ4: [answer]"""

        # Select model based on repo complexity
        model = select_model(repo_data)
        
        try:
            # Use prompt caching for system prompt (ephemeral cache)
            message = self.client.messages.create(
                model=model,
                max_tokens=250,
                temperature=0.2,
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return f"# Project Summary\n{message.content[0].text}"
            
        except Exception as e:
            try:
                # Fallback to Haiku if primary model fails
                message = self.client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=250,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return f"# Project Summary\n{message.content[0].text}"
            except:
                return f"Claude Analysis Failed: {str(e)}"