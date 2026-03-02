import requests
import re
import base64

class GitHubClient:
    def __init__(self, token=None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def parse_url(self, url):
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        return match.group(1), match.group(2)

    def get_repo_data(self, repo_url):
        owner, repo = self.parse_url(repo_url)
        
        # Fetch README
        readme_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=self.headers)
        if readme_res.status_code == 200:
            encoded = readme_res.json().get("content", "")
            try:
                # GitHub returns README content base64-encoded
                readme = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            except Exception:
                readme = ""
        else:
            readme = ""
        
        # Fetch repository tree structure
        tree_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1", headers=self.headers)
        if tree_res.status_code != 200:
            tree_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1", headers=self.headers)
        
        tree_data = tree_res.json().get("tree", []) if tree_res.status_code == 200 else []
        structure = "\n".join([file["path"] for file in tree_data[:50]])
        
        # Fetch actual code files (Python, JS, Java, etc.)
        code_files = []
        code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rb', '.php', '.scala', '.rs', '.cs']
        
        for file in tree_data[:30]:
            if file["type"] == "blob" and any(file["path"].endswith(ext) for ext in code_extensions):
                file_res = requests.get(file["url"], headers=self.headers)
                if file_res.status_code == 200:
                    content = file_res.json().get("content", "")
                    try:
                        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                        code_files.append({
                            "path": file["path"],
                            "content": decoded[:500]  # First 500 chars of each file
                        })
                    except Exception:
                        pass
        
        return {
            "readme": readme,
            "structure": structure,
            "code_files": code_files
        }