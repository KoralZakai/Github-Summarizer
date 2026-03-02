import requests
import re

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
        
        readme_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=self.headers)
        readme = readme_res.json().get("content", "") if readme_res.status_code == 200 else ""
        
        tree_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1", headers=self.headers)
        if tree_res.status_code != 200:
            tree_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1", headers=self.headers)
        
        tree_data = [file["path"] for file in tree_res.json().get("tree", [])[:50]] if tree_res.status_code == 200 else []
        
        return {
            "readme": readme,
            "structure": "\n".join(tree_data)
        }