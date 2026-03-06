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

    def clean_content(self, text):
        if not text: return ""
        
        # 1. Remove Badges (usually images with links at the top)
        text = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', '', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        
        # 2. Remove HTML comments (FIXED: was empty pattern)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # 3. Remove specific noisy sections (License, Contributors, etc.)
        # We only remove from the header until the next header
        noisy_sections = ['License', 'Contributors', 'Acknowledgments', 'Stargazers', 'Sponsors']
        for section in noisy_sections:
            pattern = rf'#+ {section}.*?(?=#+ |\Z)'
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
            
        # 4. Remove Social Media links (Twitter, Discord, etc.)
        text = re.sub(r'\[.*?\]\(https?://(?:twitter\.com|discord\.gg|t\.me).*?\)', '', text)
        
        # 5. Collapse excessive whitespace (multiple blank lines become single blank line)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

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
        """Selective tree exploration: Fetch root first, then hot directories only"""
        # Common "hot" directories that contain actual code/content
        hot_dirs = {'src', 'app', 'lib', 'components', 'utils', 'server', 'client', 
                    'backend', 'frontend', 'packages', 'modules', 'services', 'core'}
        
        for branch in ['main', 'master']:
            try:
                combined_tree = []
                
                # STEP 1: Fetch root level (non-recursive) to identify structure
                root_res = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}",
                    headers=self.headers, timeout=5
                )
                
                if root_res.status_code != 200:
                    continue
                
                root_tree = root_res.json().get("tree", [])
                combined_tree.extend(root_tree)
                
                # STEP 2: Identify hot directories present at root level
                root_dirs = {item.get('path') for item in root_tree if item.get('type') == 'tree'}
                hot_dirs_found = root_dirs & hot_dirs
                
                # STEP 3: Selectively fetch sub-trees for hot directories
                # This avoids fetching massive repos entirely
                for dir_name in hot_dirs_found:
                    try:
                        subtree_res = requests.get(
                            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}:{dir_name}?recursive=1",
                            headers=self.headers, timeout=5
                        )
                        if subtree_res.status_code == 200:
                            subtree_data = subtree_res.json().get("tree", [])
                            # Prefix paths with directory name to maintain structure
                            for item in subtree_data:
                                item['path'] = f"{dir_name}/{item['path']}"
                            combined_tree.extend(subtree_data)
                    except Exception:
                        pass
                
                # If hot dirs found and fetched, we have good coverage
                if combined_tree and hot_dirs_found:
                    return combined_tree
                    
                # Fallback: If no hot dirs found, do a full recursive fetch
                # (for repos with unusual structure)
                fallback_res = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
                    headers=self.headers, timeout=5
                )
                if fallback_res.status_code == 200:
                    return fallback_res.json().get("tree", [])
                    
            except Exception:
                pass
        
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
        
        # Smart content filtering: Remove noise (URLs, badges, boilerplate) BEFORE truncating
        # This saves 15-20% of token budget without losing technical value
        cleaned_readme = self.clean_content(raw_readme)

        return {
            "readme": self.truncate_content(cleaned_readme, max_tokens=readme_budget),
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