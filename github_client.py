import requests
import re
import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

class GitHubClient:
    def __init__(self, token=None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
        
        self.exclude_dirs = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv', 'venv', '.next', 'target', 'coverage', '.gradle', 'out', '.nuxt', '.vercel', 'gradlew', 'vendor', '.env', 'env', 'tmp', 'temp'}
        self.code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rb', '.php', '.scala', '.rs', '.cs']
        self.manifest_files = {'package.json': 'javascript', 'requirements.txt': 'python', 'pyproject.toml': 'python', 'go.mod': 'go', 'Dockerfile': 'docker', 'pom.xml': 'java', 'Gemfile': 'ruby', 'Cargo.toml': 'rust', '.csproj': 'csharp', 'build.gradle': 'java', '.gitignore': 'config'}
        self.test_patterns = ['.test.py', '_test.py', 'test_.py', '.test.js', '_test.js', '.spec.js', '.test.ts', '_test.ts', 'test.go', '_test.rs']
        self.entry_patterns = [('app.py', 0), ('main.py', 0), ('__main__.py', 1), ('app.js', 0), ('main.js', 0), ('index.js', 1), ('server.js', 0), ('main.go', 0), ('main.ts', 0), ('index.ts', 1), ('Main.java', 0), ('Application.java', 1)]

    def parse_url(self, url):
        """Extract owner and repo from GitHub URL"""
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        return match.group(1), match.group(2)

    def estimate_tokens(self, text):
        """Estimate token count using word-based heuristic (~1.3 tokens per word)"""
        if not text:
            return 0
        return int(len(str(text).split()) * 1.3) if isinstance(text, str) else int(text / 4)

    def truncate_content(self, text, max_tokens=400):
        """Truncate text to max tokens while preserving complete sentences"""
        if not text or self.estimate_tokens(text) <= max_tokens:
            return text or ""
        
        sentences = text.split('. ')
        result, current_tokens = [], 0
        
        for sentence in sentences:
            sentence_tokens = self.estimate_tokens(sentence)
            if current_tokens + sentence_tokens <= max_tokens:
                result.append(sentence)
                current_tokens += sentence_tokens
            else:
                break
        
        return '. '.join(result) + ('.' if result else '')

    def filter_tree_by_directory(self, tree_data):
        """Filter out excluded directories from tree"""
        return [f for f in tree_data if not any(f"/{exc}/" in f"/{f.get('path', '')}" or f.get('path', '').startswith(f"{exc}/") for exc in self.exclude_dirs)]

    def _fetch_readme(self, owner, repo):
        """Fetch README from GitHub API or raw content"""
        try:
            res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=self.headers, timeout=5)
            if res.status_code == 200:
                return base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
        except:
            pass
        
        for branch in ['main', 'master']:
            for readme_name in ['README.md', 'README.rst', 'README.txt', 'README']:
                try:
                    res = requests.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{readme_name}", timeout=5)
                    if res.status_code == 200:
                        return res.text
                except:
                    pass
        return ""

    def _fetch_tree(self, owner, repo):
        """Fetch repo tree structure"""
        for branch in ['main', 'master']:
            try:
                res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", headers=self.headers, timeout=5)
                if res.status_code == 200:
                    return res.json().get("tree", [])
            except:
                pass
        return []

    def get_initial_context(self, owner, repo):
        """PHASE 1: Fetch README, tree structure, and manifest files"""
        with ThreadPoolExecutor(max_workers=2) as executor:
            readme = executor.submit(self._fetch_readme, owner, repo).result()
            tree_data = executor.submit(self._fetch_tree, owner, repo).result()
        
        filtered_tree = self.filter_tree_by_directory(tree_data)
        return {
            "readme": self.truncate_content(readme, max_tokens=400),
            "structure": "\n".join([f["path"] for f in filtered_tree[:100]]),
            "tree_data": filtered_tree
        }

    def get_manifest_files(self, owner, repo, tree_data):
        """PHASE 1: Extract manifest files"""
        manifests = {}
        priority_order = ['package.json', 'requirements.txt', 'pyproject.toml', 'go.mod', 'Dockerfile', 'pom.xml']
        
        for manifest_name in priority_order[:3]:
            for file in tree_data[:50]:
                if file["path"].endswith(manifest_name):
                    try:
                        res = requests.get(file["url"], headers=self.headers, timeout=5)
                        if res.status_code == 200:
                            decoded = base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
                            manifests[manifest_name] = self.truncate_content(decoded, max_tokens=200)
                            break
                    except:
                        pass
        return manifests

    def scan_readme_for_hints(self, readme_text):
        """PHASE 2: Extract file name hints from README"""
        if not readme_text:
            return []
        hints = []
        keywords = ['entry point', 'main', 'start with', 'getting started', 'implementation', 'architecture', 'quickstart']
        for line in readme_text.split('\n'):
            if any(kw in line.lower() for kw in keywords):
                files = re.findall(r'\b([a-z_][a-z0-9_]*\.(py|js|ts|go|java|rs|rb|php))\b', line, re.IGNORECASE)
                hints.extend([f[0] for f in files])
        return list(set(hints[:10]))

    def find_entry_points(self, tree_data):
        """PHASE 2: Identify likely entry point files"""
        found = [(f.get("path", ""), p) for f in tree_data[:30] for pattern, p in self.entry_patterns if f.get("path", "").endswith(pattern)]
        found.sort(key=lambda x: (x[1], x[0].count('/')))
        return [p[0] for p in found[:5]]

    def extract_tech_stack(self, manifests, tree_data):
        """PHASE 2: Identify primary languages and frameworks"""
        languages, frameworks, key_deps = set(), set(), []
        
        if 'package.json' in manifests:
            languages.add("JavaScript/TypeScript")
            try:
                data = json.loads(manifests['package.json'][:500])
                key_deps.extend(list(data.get('dependencies', {}).keys())[:5])
            except:
                pass
        
        if 'requirements.txt' in manifests:
            languages.add("Python")
            for line in manifests['requirements.txt'].split('\n'):
                pkg = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                if pkg and not line.startswith('#'):
                    key_deps.append(pkg)
                    if any(fw in line.lower() for fw in ['django', 'flask', 'fastapi', 'pytest', 'uvicorn']):
                        frameworks.add(line.split('==')[0].strip().title())
        
        if 'go.mod' in manifests:
            languages.add("Go")
        if 'pom.xml' in manifests:
            languages.add("Java")
        if 'Dockerfile' in manifests:
            for line in manifests['Dockerfile'].split('\n'):
                if line.startswith('FROM'):
                    frameworks.add(line.split()[1].split(':')[0])
        
        ext_count = {}
        for file in tree_data[:50]:
            for ext in self.code_extensions:
                if file.get("path", "").endswith(ext):
                    ext_count[ext] = ext_count.get(ext, 0) + 1
        
        if ext_count:
            most_common = max(ext_count, key=ext_count.get)
            lang_map = {'.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.go': 'Go', '.java': 'Java', '.rs': 'Rust', '.rb': 'Ruby'}
            languages.add(lang_map.get(most_common, most_common))
        
        return {"languages": list(languages), "frameworks": list(frameworks), "key_deps": key_deps[:10]}

    def sample_code_files(self, tree_data, entry_points, hint_files, max_tokens=300):
        """PHASE 3: Intelligently sample code files"""
        code_files = []
        current_tokens = 0
        priority_files = set(entry_points + hint_files)
        
        for file in tree_data[:30]:
            if current_tokens >= max_tokens or len(code_files) >= 5:
                break
            try:
                path = file.get("path", "")
                if any(path.endswith(ext) for ext in self.code_extensions):
                    res = requests.get(file["url"], headers=self.headers, timeout=5)
                    if res.status_code == 200:
                        decoded = base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
                        file_tokens = self.estimate_tokens(decoded)
                        if current_tokens + file_tokens <= max_tokens:
                            code_files.append({"path": path, "content": decoded[:500]})
                            current_tokens += file_tokens
            except:
                pass
        return code_files

    def fetch_test_context(self, owner, repo, tree_data, max_tokens=150):
        """PHASE 3: Fetch test files"""
        test_files, current_tokens = [], 0
        for file in tree_data[:100]:
            if current_tokens >= max_tokens or len(test_files) >= 2:
                break
            try:
                path = file.get("path", "")
                if any(p in path for p in self.test_patterns) and file.get("type") == "blob":
                    res = requests.get(file["url"], headers=self.headers, timeout=5)
                    if res.status_code == 200:
                        decoded = base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")[:300]
                        file_tokens = self.estimate_tokens(decoded)
                        if current_tokens + file_tokens <= max_tokens:
                            test_files.append({"path": path, "content": decoded})
                            current_tokens += file_tokens
            except:
                pass
        return test_files

    def get_repo_data(self, repo_url):
        """Main orchestration: Execute all phases"""
        owner, repo = self.parse_url(repo_url)
        
        initial_context = self.get_initial_context(owner, repo)
        manifests = self.get_manifest_files(owner, repo, initial_context["tree_data"])
        
        entry_points = self.find_entry_points(initial_context["tree_data"])
        hints = self.scan_readme_for_hints(initial_context["readme"])
        tech_stack = self.extract_tech_stack(manifests, initial_context["tree_data"])
        
        code_files = self.sample_code_files(initial_context["tree_data"], entry_points, hints, max_tokens=300)
        code_files.extend(self.fetch_test_context(owner, repo, initial_context["tree_data"]))
        
        return {
            "readme": initial_context["readme"],
            "structure": initial_context["structure"],
            "code_files": code_files,
            "_metadata": {"tech_stack": tech_stack, "manifests": manifests, "entry_points": entry_points, "hints": hints}
        }