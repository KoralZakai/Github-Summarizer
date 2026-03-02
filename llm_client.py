import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key and self.api_key != "mock":
            self.client = Anthropic(api_key=self.api_key)

    def summarize(self, repo_data):
        if not self.api_key or self.api_key == "mock":
            return "# Project Summary (Mock)\nFalling back to local analysis."

        # Build code analysis from actual files
        code_analysis = ""
        if repo_data.get("code_files"):
            code_analysis = "\n\nActual Code Files Analysis:\n"
            for file in repo_data["code_files"][:5]:
                code_analysis += f"File: {file['path']}\n{file['content']}\n"
        
        # Handle README - may be empty
        # readme_text = repo_data.get("readme", "").strip()
        readme_text = ""
        readme_section = f"README Content:\n{readme_text[:1000]}" if readme_text else "No README file found"
        print(readme_section)
        prompt = f"""Analyze this GitHub repository and provide a concise summary. Use clear, plain text formatting without special characters or markdown symbols.

Repository Structure:
{repo_data.get('structure', 'No structure available')}

{readme_section}

{code_analysis}

Answer these 4 questions clearly and concisely:

1. WHO SHOULD USE THIS REPO - Describe the target audience or users (developers, data scientists, system administrators, etc.)

2. WHY AND FOR WHAT PURPOSE - Explain what problems it solves and why someone would use it

3. INPUT AND OUTPUT - List what the project accepts as input and what it produces/returns

4. LANGUAGE AND CODE - List the programming languages used and key technologies

Use simple, direct language without lists or bullet points. Write 1-2 sentences per question."""

        try:
    
            message = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                temperature=0.2,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return f"# Project Summary\n{message.content[0].text}"
            
        except Exception as e:
          
            try:
                message = self.client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except:
                return f"Claude Analysis Failed: {str(e)}"