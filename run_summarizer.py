#!/usr/bin/env python3
"""
Simple CLI for testing GitHub repository summaries
Strategy: Use intelligent repo analysis with token budget optimization
"""

import sys
import time
from datetime import datetime
from github_client import GitHubClient
from llm_client import LLMClient

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(text.center(70))
    print("="*70)

def print_section(title):
    """Print formatted section"""
    print(f"\n{title}")
    print("-" * 70)

def run_summary(repo_url):
    """Run optimized summarization with smart token budget management"""
    
    print_header("GITHUB REPOSITORY SUMMARIZER (OPTIMIZED)")
    print(f"\nRepository: {repo_url}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    gh_client = GitHubClient()
    llm_client = LLMClient()
    
    try:
        # Parse URL
        owner, repo = gh_client.parse_url(repo_url)
        print(f"Analyzing: {owner}/{repo}")
        
        # Step 1: Run all 4 phases of intelligent extraction
        start_fetch = time.time()
        print("\n[Phase 1] Fetching initial context and manifests...")
        
        repo_data = gh_client.get_repo_data(repo_url)
        fetch_time = time.time() - start_fetch
        
        # Extract metrics
        readme = repo_data.get('readme', '')
        structure = repo_data.get('structure', '')
        code_files = repo_data.get('code_files', [])
        metadata = repo_data.get('_metadata', {})
        
        readme_size = len(readme) if readme else 0
        code_files_count = len(code_files)
        
        print(f"  ✓ README size: {readme_size} chars")
        print(f"  ✓ Code files sampled: {code_files_count}")
        print(f"  ✓ Tech stack identified: {', '.join(metadata.get('tech_stack', {}).get('languages', []))}")
        
        # Step 2: Generate summary with agentic feedback
        print("\n[Phase 2] Generating summary with Claude Haiku...")
        start_summary = time.time()
        
        summary = llm_client.summarize(repo_data, gh_client=gh_client)
        summary_time = time.time() - start_summary
        
        # Step 3: Display results
        print_section("FINAL SUMMARY")
        print(summary)
        
        # Step 4: Display metrics
        print_section("PERFORMANCE METRICS")
        
        total_time = fetch_time + summary_time
        summary_str = str(summary) if summary else ""
        
        input_chars = readme_size + len(structure)
        output_chars = len(summary_str)
        
        input_tokens = gh_client.estimate_tokens(input_chars)
        output_tokens = gh_client.estimate_tokens(output_chars)
        total_tokens = input_tokens + output_tokens
        
        # Get actual token usage from LLM
        actual_usage = llm_client.get_token_usage()
        
        # Calculate cost (Haiku pricing: $0.80 per 1M input, $2.40 per 1M output)
        estimated_cost = (actual_usage.get("input_tokens", input_tokens) * 0.80 + 
                         actual_usage.get("output_tokens", output_tokens) * 2.40) / 1_000_000
        
        print(f"Total Time: {total_time:.3f}s (fetch: {fetch_time:.3f}s, LLM: {summary_time:.3f}s)")
        print(f"Input Tokens (estimated): {actual_usage.get('input_tokens', input_tokens)}")
        print(f"Output Tokens: {actual_usage.get('output_tokens', output_tokens)}")
        print(f"Total Tokens: {total_tokens}")
        print(f"Estimated Cost: ${estimated_cost:.6f}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        print("\n✓ SUCCESS - Summary generated with intelligent optimization")
        print("="*70 + "\n")
        
        return True
        
    except ValueError as e:
        print(f"\n✗ ERROR: Invalid GitHub URL")
        print(f"  {str(e)}")
        print(f"  Expected: https://github.com/owner/repo")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        print(f"\nCheck:")
        print(f"  - GitHub URL is valid and public")
        print(f"  - ANTHROPIC_API_KEY is set in .env")
        print(f"  - Internet connection is working")
        return False

def print_usage():
    """Print usage instructions"""
    print_header("USAGE")
    print("""
Examples:
    python run_summarizer.py https://github.com/pallets/flask
    python run_summarizer.py https://github.com/tornadoweb/tornado
    python run_summarizer.py https://github.com/psf/requests

The script will intelligently:
  1. Fetch README and repository structure
  2. Identify manifest files (package.json, requirements.txt, etc.)
  3. Scan for entry points and tech stack
  4. Sample important code files (full or signatures only)
  5. Fetch test context to understand expected behavior
  6. Ask LLM if additional files are needed (agentic feedback)
  7. Generate comprehensive summary

Output includes execution time, token usage, and estimated cost.
Smart optimization ensures minimal token usage (~1000 input tokens).
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    repo_url = sys.argv[1]
    
    # Validate URL format
    if not repo_url.startswith("https://github.com/"):
        print(f"\n✗ ERROR: Invalid URL: {repo_url}")
        print(f"  Expected: https://github.com/owner/repo")
        print_usage()
        sys.exit(1)
    
    success = run_summary(repo_url)
    sys.exit(0 if success else 1)
