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
        
        # Configuration
        self.exclude_dirs = {
            '.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv', 
            'venv', '.next', 'target', 'coverage', '.gradle', 'out', '.nuxt',
            '.vercel', 'gradlew', 'vendor', '.env', 'env', 'tmp', 'temp'
        }
        self.code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rb', '.php', '.scala', '.rs', '.cs']
        self.manifest_files = {
            'package.json': 'javascript',
            'requirements.txt': 'python',
            'pyproject.toml': 'python',
            'go.mod': 'go',
            'Dockerfile': 'docker',
            'pom.xml': 'java',
            'Gemfile': 'ruby',
            'Cargo.toml': 'rust',
            '.csproj': 'csharp',
            'build.gradle': 'java',
            '.gitignore': 'config'
        }

    def parse_url(self, url):
        """Extract owner and repo from GitHub URL"""
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        return match.group(1), match.group(2)

    def estimate_tokens(self, text):
        """Estimate token count using word-based heuristic (~1.3 tokens per word)"""
        if text is None or text == 0 or text == "":
            return 0
        # Convert to string if integer (char count approximation)
        if isinstance(text, int):
            return int(text / 4)  # Rough approximation: 4 chars per token
        word_count = len(str(text).split())
        return int(word_count * 1.3)

    def truncate_content(self, text, max_tokens=400):
        """Truncate text to max tokens while preserving complete sentences"""
        if not text:
            return ""
        
        if self.estimate_tokens(text) <= max_tokens:
            return text
        
        sentences = text.split('. ')
        result = []
        current_tokens = 0
        
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
        filtered = []
        for file in tree_data:
            path = file.get("path", "")
            # Check if any excluded dir is in the path
            if not any(f"/{exc}/" in f"/{path}" or path.startswith(f"{exc}/") for exc in self.exclude_dirs):
                filtered.append(file)
        return filtered

    def extract_signatures(self, file_content, language=None):
        """Extract function/class signatures and docstrings from code"""
        lines = file_content.split('\n')
        signatures = []
        in_docstring = False
        docstring_char = None
        current_block = []
        
        for line in lines:
            stripped = line.strip()
            
            # Python: class/def with docstring
            if language == 'python' or (language is None and any(line.startswith(x) for x in ['class ', 'def ', 'async def '])):
                if any(stripped.startswith(x) for x in ['class ', 'def ', 'async def ']):
                    if current_block:
                        signatures.append('\n'.join(current_block))
                    current_block = [line]
                elif in_docstring:
                    current_block.append(line)
                    if docstring_char in line:
                        in_docstring = False
                elif '"""' in line or "'''" in line:
                    in_docstring = True
                    docstring_char = '"""' if '"""' in line else "'''"
                    current_block.append(line)
                elif current_block and (line == '' or line.startswith(' ')):
                    current_block.append(line)
                elif current_block:
                    break  # End of block
            
            # JavaScript/TypeScript: function/class
            elif language in ['javascript', 'typescript', None] and any(stripped.startswith(x) for x in ['function ', 'class ', 'const ', 'export ', 'async function']):
                if current_block:
                    signatures.append('\n'.join(current_block))
                current_block = [line]
                if '{' in line:
                    break
            
            # Go: func/type
            elif language == 'go' or (language is None and any(stripped.startswith(x) for x in ['func ', 'type '])):
                if any(stripped.startswith(x) for x in ['func ', 'type ']):
                    if current_block:
                        signatures.append('\n'.join(current_block))
                    current_block = [line]
                    if '{' in line:
                        break
            
            # Java: class/interface/method
            elif language == 'java' or (language is None and any(stripped.startswith(x) for x in ['public ', 'private ', 'class ', 'interface '])):
                if any(x in stripped for x in ['public ', 'private ', 'class ', 'interface ']):
                    if current_block:
                        signatures.append('\n'.join(current_block))
                    current_block = [line]
                    if '{' in line:
                        break
        
        if current_block:
            signatures.append('\n'.join(current_block))
        
        return '\n'.join(signatures[:10])  # Limit to first 10 signatures

    def get_initial_context(self, owner, repo):
        """PHASE 1: Fetch README, tree structure, and manifest files"""
        def fetch_readme():
            try:
                res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", 
                                 headers=self.headers, timeout=5)
                if res.status_code == 200:
                    encoded = res.json().get("content", "")
                    return base64.b64decode(encoded).decode("utf-8", errors="ignore")
            except Exception:
                pass
            return ""
        
        def fetch_tree():
            try:
                # Try main branch first, fallback to master
                res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1", 
                                 headers=self.headers, timeout=5)
                if res.status_code != 200:
                    res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1", 
                                     headers=self.headers, timeout=5)
                
                if res.status_code == 200:
                    return res.json().get("tree", [])
            except Exception:
                pass
            return []
        
        # Parallel fetch README and tree
        with ThreadPoolExecutor(max_workers=2) as executor:
            readme_future = executor.submit(fetch_readme)
            tree_future = executor.submit(fetch_tree)
            
            readme = readme_future.result()
            tree_data = tree_future.result()
        
        # Filter tree by directory
        filtered_tree = self.filter_tree_by_directory(tree_data)
        
        # Build structure string (limited to 100 files)
        structure = "\n".join([f["path"] for f in filtered_tree[:100]])
        
        # Truncate README to token budget
        readme = self.truncate_content(readme, max_tokens=400)
        
        return {
            "readme": readme,
            "structure": structure,
            "tree_data": filtered_tree
        }

    def get_manifest_files(self, owner, repo, tree_data):
        """PHASE 1: Extract manifest files (package.json, requirements.txt, etc.)"""
        manifests = {}
        manifest_paths = {}
        
        # Build map of manifest file names to paths in tree
        for file in tree_data[:50]:  # Only search first 50 files
            filename = file["path"].split('/')[-1]
            if filename in self.manifest_files:
                manifest_paths[filename] = file
        
        # Fetch up to 3 most important manifests
        priority_order = ['package.json', 'requirements.txt', 'pyproject.toml', 'go.mod', 'Dockerfile', 'pom.xml']
        fetch_count = 0
        
        for manifest_name in priority_order:
            if fetch_count >= 3 or manifest_name not in manifest_paths:
                continue
            
            try:
                file_data = manifest_paths[manifest_name]
                res = requests.get(file_data["url"], headers=self.headers, timeout=5)
                
                if res.status_code == 200:
                    content = res.json().get("content", "")
                    decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                    # Truncate manifest to 200 tokens
                    manifests[manifest_name] = self.truncate_content(decoded, max_tokens=200)
                    fetch_count += 1
            except Exception:
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
                # Extract potential file names (e.g., 'main.py', 'app.js')
                files = re.findall(r'\b([a-z_][a-z0-9_]*\.(py|js|ts|go|java|rs|rb|php))\b', line, re.IGNORECASE)
                hints.extend([f[0] for f in files])
        
        return list(set(hints[:10]))  # Unique, max 10

    def find_entry_points(self, tree_data):
        """PHASE 2: Identify likely entry point files"""
        entry_patterns = [
            ('app.py', 0), ('main.py', 0), ('__main__.py', 1),
            ('app.js', 0), ('main.js', 0), ('index.js', 1), ('server.js', 0),
            ('main.go', 0), ('main.ts', 0), ('index.ts', 1),
            ('Main.java', 0), ('Application.java', 1),
        ]
        
        found = []
        for file in tree_data[:30]:
            path = file.get("path", "")
            basename = path.split('/')[-1]
            
            for pattern, priority in entry_patterns:
                if basename == pattern:
                    found.append((path, priority))
        
        # Sort by priority, then by path depth
        found.sort(key=lambda x: (x[1], x[0].count('/')))
        return [p[0] for p in found[:5]]  # Return top 5

    def extract_tech_stack(self, manifests, tree_data):
        """PHASE 2: Identify primary languages and frameworks"""
        tech_stack = {
            "languages": set(),
            "frameworks": set(),
            "key_deps": []
        }
        
        # Infer from manifests
        for manifest_name, content in manifests.items():
            if manifest_name == 'package.json':
                tech_stack["languages"].add("JavaScript/TypeScript")
                try:
                    data = json.loads(content[:500])  # Parse first 500 chars
                    if 'dependencies' in data:
                        deps = list(data['dependencies'].keys())[:5]
                        tech_stack["key_deps"].extend(deps)
                except:
                    pass
            elif manifest_name == 'requirements.txt':
                tech_stack["languages"].add("Python")
                frameworks = ['django', 'flask', 'fastapi', 'pytest']
                for line in content.split('\n'):
                    for fw in frameworks:
                        if fw.lower() in line.lower():
                            tech_stack["frameworks"].add(fw.title())
            elif manifest_name == 'go.mod':
                tech_stack["languages"].add("Go")
            elif manifest_name == 'pom.xml':
                tech_stack["languages"].add("Java")
            elif manifest_name == 'Dockerfile':
                # Extract base image
                for line in content.split('\n'):
                    if line.startswith('FROM'):
                        tech_stack["frameworks"].add(line.split()[1].split(':')[0])
        
        # Infer from file extensions
        ext_count = {}
        for file in tree_data[:50]:
            path = file.get("path", "")
            for ext in self.code_extensions:
                if path.endswith(ext):
                    ext_count[ext] = ext_count.get(ext, 0) + 1
        
        if ext_count:
            most_common = max(ext_count, key=ext_count.get)
            lang_map = {
                '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
                '.go': 'Go', '.java': 'Java', '.rs': 'Rust', '.rb': 'Ruby'
            }
            tech_stack["languages"].add(lang_map.get(most_common, most_common))
        
        return {
            "languages": list(tech_stack["languages"]),
            "frameworks": list(tech_stack["frameworks"]),
            "key_deps": tech_stack["key_deps"]
        }

    def sample_code_files(self, tree_data, entry_points, hint_files, max_tokens=300):
        """PHASE 3: Intelligently sample code files (signatures if >100 lines)"""
        code_files = []
        current_tokens = 0
        fetched_paths = set()
        
        # Prioritize: entry points → hints → test files → remaining code
        priority_files = entry_points + hint_files
        remaining_files = [f for f in tree_data if f['type'] == 'blob' and 
                          any(f['path'].endswith(ext) for ext in self.code_extensions)]
        
        # Sort by priority
        def priority_key(file_path):
            for i, p in enumerate(priority_files):
                if p in file_path:
                    return (0, i)  # High priority
            return (1, 0)  # Low priority
        
        remaining_files.sort(key=lambda f: priority_key(f.get("path", "")))
        
        all_candidate_files = [f for f in remaining_files if f.get("path") in priority_files or f in remaining_files]
        
        for file in all_candidate_files[:30]:  # Limit iterations
            if current_tokens >= max_tokens or len(code_files) >= 5:
                break
            
            try:
                path = file.get("path", "")
                if path in fetched_paths:
                    continue
                
                res = requests.get(file["url"], headers=self.headers, timeout=5)
                if res.status_code == 200:
                    content = res.json().get("content", "")
                    decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                    
                    # If file > 100 lines, extract signatures only
                    if len(decoded.split('\n')) > 100:
                        decoded = self.extract_signatures(decoded)
                    
                    file_tokens = self.estimate_tokens(decoded)
                    if current_tokens + file_tokens <= max_tokens:
                        code_files.append({
                            "path": path,
                            "content": decoded[:500]
                        })
                        current_tokens += file_tokens
                        fetched_paths.add(path)
            except Exception:
                pass
        
        return code_files

    def fetch_test_context(self, owner, repo, tree_data, max_tokens=150):
        """PHASE 3: Fetch test files to understand expected behavior"""
        test_patterns = ['.test.py', '_test.py', 'test_.py', '.test.js', '_test.js', 
                        '.spec.js', '.test.ts', '_test.ts', 'test.go', '_test.rs']
        test_files = []
        current_tokens = 0
        
        for file in tree_data[:100]:
            if current_tokens >= max_tokens or len(test_files) >= 2:
                break
            
            try:
                path = file.get("path", "")
                if any(pattern in path for pattern in test_patterns) and file.get("type") == "blob":
                    res = requests.get(file["url"], headers=self.headers, timeout=5)
                    if res.status_code == 200:
                        content = res.json().get("content", "")
                        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                        
                        # Extract test names/descriptions only (first 300 chars)
                        test_summary = decoded[:300]
                        file_tokens = self.estimate_tokens(test_summary)
                        
                        if current_tokens + file_tokens <= max_tokens:
                            test_files.append({
                                "path": path,
                                "content": test_summary
                            })
                            current_tokens += file_tokens
            except Exception:
                pass
        
        return test_files

    def request_missing_info(self, llm_client, collected_data):
        """PHASE 4: Ask LLM if specific files are needed for completion"""
        # This will be called from llm_client after initial summary
        # Prepare structured query for LLM
        return {
            "query": "Based on the repository structure and manifests provided, are there specific files you need to read to complete the comprehensive summary? List file paths.",
            "context": collected_data
        }

    def get_repo_data(self, repo_url):
        """Main orchestration: Execute all 4 phases in sequence"""
        owner, repo = self.parse_url(repo_url)
        
        # PHASE 1: Initial context
        initial_context = self.get_initial_context(owner, repo)
        manifests = self.get_manifest_files(owner, repo, initial_context["tree_data"])
        
        # PHASE 2: Metadata & hints
        hints = self.scan_readme_for_hints(initial_context["readme"])
        entry_points = self.find_entry_points(initial_context["tree_data"])
        tech_stack = self.extract_tech_stack(manifests, initial_context["tree_data"])
        
        # PHASE 3: Code sampling
        code_files = self.sample_code_files(
            initial_context["tree_data"], 
            entry_points, 
            hints, 
            max_tokens=300
        )
        test_context = self.fetch_test_context(owner, repo, initial_context["tree_data"])
        
        # Merge code files and test context
        code_files.extend(test_context)
        
        # Return backward-compatible format
        return {
            "readme": initial_context["readme"],
            "structure": initial_context["structure"],
            "code_files": code_files,
            # Additional metadata for enhanced summarization
            "_metadata": {
                "tech_stack": tech_stack,
                "manifests": manifests,
                "entry_points": entry_points,
                "hints": hints
            }
        }