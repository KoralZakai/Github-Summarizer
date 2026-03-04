import requests
import re
import base64

def find_entry_points(code_files):
    """Extract only essential entry point files for analysis"""
    entry_patterns = ['main.py', 'app.py', '__init__.py', 'setup.py', 'index.js', 
                     'package.json', 'Dockerfile', 'requirements.txt', 'pom.xml', 'build.gradle']
    
    entry_files = []
    for file in code_files:
        if any(pattern in file['path'] for pattern in entry_patterns):
            entry_files.append(file)
    
    # If no entry points found, take first 3 files
    if not entry_files:
        entry_files = code_files[:3]
    
    return entry_files[:4]  # Return max 4 files

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
        
        # Fetch repository tree structure (optimized: only first 15 lines for summary)
        tree_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1", headers=self.headers)
        if tree_res.status_code != 200:
            tree_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1", headers=self.headers)
        
        tree_data = tree_res.json().get("tree", []) if tree_res.status_code == 200 else []
        structure = "\n".join([file["path"] for file in tree_data[:15]])  # Reduced from 50 to 15
        
        # Fetch actual code files - simplified approach
        code_files = []
        code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rb', '.php', '.scala', '.rs', '.cs', '.yml', '.yaml']
        
        # Look for code files in the tree data (don't fetch individually)
        for file in tree_data[:100]:  # Look through more files
            if file.get("type") == "blob" and any(file.get("path", "").endswith(ext) for ext in code_extensions):
                # Get raw file content from GitHub
                file_path = file.get("path", "")
                try:
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_path}"
                    # Try main branch first
                    file_res = requests.get(raw_url, headers=self.headers, timeout=5)
                    if file_res.status_code != 200:
                        # Try master branch
                        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}"
                        file_res = requests.get(raw_url, headers=self.headers, timeout=5)
                    
                    if file_res.status_code == 200:
                        content = file_res.text[:200]  # Get first 200 chars
                        code_files.append({
                            "path": file_path,
                            "content": content
                        })
                    
                    if len(code_files) >= 5:  # Stop after finding 5 files
                        break
                except Exception:
                    pass
        
        # Filter to only essential entry point files
        key_files = find_entry_points(code_files) if code_files else code_files[:3]
        
        return {
            "readme": readme,
            "structure": structure,
            "code_files": key_files  # Only 3-4 essential files instead of all
        }