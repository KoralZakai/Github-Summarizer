import requests
import re
import base64
import json
from concurrent.futures import ThreadPoolExecutor

class GitHubClient:
    def __init__(self, token=None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
        
        self.exclude_dirs = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv', 'venv', '.next', 'target', 'coverage'}
        self.code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rb', '.php', '.scala', '.rs', '.cs']
        self.manifest_files = {
            'package.json': 'javascript', 'requirements.txt': 'python', 
            'pyproject.toml': 'python', 'go.mod': 'go', 'Dockerfile': 'docker', 
            'pom.xml': 'java', 'Gemfile': 'ruby', 'Cargo.toml': 'rust'
        }
        self.test_patterns = ['.test.py', '_test.py', 'test_.py', '.test.js', '.spec.js']
        self.entry_patterns = [
            ('app.py', 0), ('main.py', 0), ('__main__.py', 1), 
            ('index.js', 1), ('server.js', 0), ('main.go', 0)
        ]

    def parse_url(self, url):
        """Extract owner and repo from GitHub URL"""
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        return match.group(1), match.group(2)

    def estimate_tokens(self, text):
        """Word-based token heuristic"""
        if not text: return 0
        return int(len(str(text).split()) * 1.3)

    def truncate_content(self, text, max_tokens=400):
        """Truncate text while preserving sentences"""
        if not text or self.estimate_tokens(text) <= max_tokens:
            return text or ""
        sentences = text.split('. ')
        result, current_tokens = [], 0
        for sentence in sentences:
            sentence_tokens = self.estimate_tokens(sentence)
            if current_tokens + sentence_tokens <= max_tokens:
                result.append(sentence)
                current_tokens += sentence_tokens
            else: break
        return '. '.join(result) + "..."

    def filter_tree_by_directory(self, tree_data):
        """Filter excluded directories"""
        return [f for f in tree_data if not any(f"/{exc}/" in f"/{f.get('path', '')}" or f.get('path', '').startswith(f"{exc}/") for exc in self.exclude_dirs)]

    def _fetch_readme(self, owner, repo):
        try:
            res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=self.headers, timeout=5)
            if res.status_code == 200:
                return base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
        except: pass
        return ""

    def _fetch_tree(self, owner, repo):
        for branch in ['main', 'master']:
            try:
                res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", headers=self.headers, timeout=5)
                if res.status_code == 200:
                    return res.json().get("tree", [])
            except: pass
        return []

    def extract_tech_stack(self, tree_data):
        """Original language/tech detection logic"""
        languages = set()
        ext_count = {}
        for file in tree_data[:100]:
            path = file.get("path", "")
            for ext in self.code_extensions:
                if path.endswith(ext):
                    ext_count[ext] = ext_count.get(ext, 0) + 1
        
        if ext_count:
            lang_map = {'.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.go': 'Go', '.java': 'Java'}
            for ext in ext_count:
                if ext in lang_map: languages.add(lang_map[ext])
        
        if not languages:
            languages.add("Documentation/Quiz Content")
        return {"languages": list(languages)}

    def sample_code_files(self, tree_data, owner, repo, max_tokens=300):
        """FIX: Fetch actual file content using raw GitHub URLs"""
        code_files = []
        current_tokens = 0
        
        for file in tree_data:
            if current_tokens >= max_tokens or len(code_files) >= 5: 
                break
                
            path = file.get("path", "")
            if any(path.endswith(ext) for ext in self.code_extensions) and file.get("type") == "blob":
                try:
                    # Use raw GitHub URL instead of API tree URL
                    for branch in ['main', 'master']:
                        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
                        res = requests.get(raw_url, headers=self.headers, timeout=5)
                        
                        if res.status_code == 200:
                            content = res.text
                            truncated = self.truncate_content(content, max_tokens=500)
                            code_files.append({
                                "path": path, 
                                "content": truncated
                            })
                            current_tokens += self.estimate_tokens(truncated)
                            break
                except Exception as e: 
                    continue
                    
        return code_files

    def get_repo_data(self, repo_url):
        """Orchestration with Static Analysis and Dynamic Budgeting"""
        owner, repo = self.parse_url(repo_url)
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            raw_readme = executor.submit(self._fetch_readme, owner, repo).result()
            tree_data = executor.submit(self._fetch_tree, owner, repo).result()
        
        filtered_tree = self.filter_tree_by_directory(tree_data)
        tech_stack = self.extract_tech_stack(filtered_tree)
        
        # DYNAMIC BUDGETING: Check if it's content-heavy vs code-heavy
        is_content_repo = "Documentation/Quiz Content" in tech_stack["languages"]
        readme_budget = 5000 if is_content_repo else 800
        code_budget = 200 if is_content_repo else 1500

        # Sample code files using the budget - PASS owner and repo
        code_files = self.sample_code_files(filtered_tree, owner, repo, max_tokens=code_budget)

        return {
            "readme": self.truncate_content(raw_readme, max_tokens=readme_budget),
            "structure": "\n".join([f["path"] for f in filtered_tree[:100]]),
            "tree_data": filtered_tree,
            "code_files": code_files,
            "_metadata": {
                "owner": owner, 
                "repo": repo, 
                "tech_stack": tech_stack,
                "is_content_only": is_content_repo
            }
        }