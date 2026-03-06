#!/usr/bin/env python3
"""
Simple CLI for testing GitHub repository summaries
Strategy: Use intelligent repo analysis with token budget optimization
"""

import sys
import time
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from github_client import GitHubClient
from llm_client import LLMClient

# Cache configuration
CACHE_DB = "summary_cache.db"

def init_cache_db():
    """Initialize SQLite cache database"""
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            url_hash TEXT PRIMARY KEY,
            repo_url TEXT UNIQUE,
            summary TEXT,
            metadata TEXT,
            created_at TIMESTAMP,
            accessed_count INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

def get_cache_key(repo_url):
    """Generate a hash key for the repository URL"""
    return hashlib.md5(repo_url.encode()).hexdigest()

def get_cached_summary(repo_url):
    """Retrieve summary from cache if it exists"""
    init_cache_db()
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT summary, metadata, accessed_count FROM summaries WHERE repo_url = ?",
        (repo_url,)
    )
    row = cursor.fetchone()
    
    if row:
        summary, metadata, accessed_count = row
        # Update access count
        cursor.execute(
            "UPDATE summaries SET accessed_count = ? WHERE repo_url = ?",
            (accessed_count + 1, repo_url)
        )
        conn.commit()
        conn.close()
        return summary, metadata, accessed_count + 1
    
    conn.close()
    return None, None, 0

def cache_summary(repo_url, summary, metadata):
    """Store summary in cache"""
    init_cache_db()
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO summaries 
            (url_hash, repo_url, summary, metadata, created_at, accessed_count)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            get_cache_key(repo_url),
            repo_url,
            summary,
            metadata,
            datetime.now().isoformat()
        ))
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        conn.close()

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
        
        # CACHE CHECK: Look for existing summary
        cached_summary, cached_metadata, access_count = get_cached_summary(repo_url)
        
        if cached_summary:
            print(f"\n[CACHE HIT] 🚀 Returning cached summary (accessed {access_count} times)")
            print_section("FINAL SUMMARY (FROM CACHE)")
            print(cached_summary)
            
            # Parse and display cached metrics
            import json
            try:
                metadata = json.loads(cached_metadata)
                print_section("PERFORMANCE METRICS (CACHED)")
                print(f"Total Time: {metadata.get('total_time', 0):.3f}s (instant from cache)")
                print(f"Input Tokens: {metadata.get('input_tokens', 0)}")
                print(f"Output Tokens: {metadata.get('output_tokens', 0)}")
                print(f"Total Tokens: {metadata.get('total_tokens', 0)}")
                print(f"Estimated Cost: ${metadata.get('estimated_cost', 0):.6f}")
                print(f"Cached on: {metadata.get('cached_at', 'Unknown')}")
                print(f"Original fetch time: {metadata.get('fetch_time', 0):.3f}s")
                print(f"Original LLM time: {metadata.get('summary_time', 0):.3f}s")
            except:
                pass
            
            print("\n[SUCCESS] Retrieved from cache")
            print("="*70 + "\n")
            return True
        
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
        
        print(f"  [OK] README size: {readme_size} chars")
        print(f"  [OK] Code files sampled: {code_files_count}")
        print(f"  [OK] Tech stack identified: {', '.join(metadata.get('tech_stack', {}).get('languages', []))}")
        
        # Step 2: Generate summary with agentic feedback (streamed)
        print("\n[Phase 2] Generating summary with Claude Haiku...")
        print_section("STREAMING SUMMARY...")
        
        start_summary = time.time()
        summary_str = ""
        
        # Consume the streaming generator and print chunks in real-time
        for chunk in llm_client.summarize(repo_data, gh_client=gh_client):
            summary_str += chunk
            # Print chunk immediately without buffering for instant feedback
            sys.stdout.write(chunk)
            sys.stdout.flush()
        
        summary_time = time.time() - start_summary
        print()  # newline after streaming content
        
        # Step 4: Display metrics
        print_section("PERFORMANCE METRICS")
        
        total_time = fetch_time + summary_time
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
        
        # CACHE STORAGE: Store the summary for future requests
        import json
        cache_metadata = json.dumps({
            'total_time': total_time,
            'fetch_time': fetch_time,
            'summary_time': summary_time,
            'input_tokens': actual_usage.get('input_tokens', input_tokens),
            'output_tokens': actual_usage.get('output_tokens', output_tokens),
            'total_tokens': total_tokens,
            'estimated_cost': estimated_cost,
            'cached_at': datetime.now().isoformat(),
            'tech_stack': metadata.get('tech_stack', {})
        })
        cache_summary(repo_url, summary_str, cache_metadata)
        print("\n[CACHE] Summary stored for future requests")
        
        print("\n[SUCCESS] Summary generated with intelligent optimization")
        print("="*70 + "\n")
        
        return True
        
    except ValueError as e:
        print(f"\n[ERROR] Invalid GitHub URL")
        print(f"  {str(e)}")
        print(f"  Expected: https://github.com/owner/repo")
        return False
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
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
  1. Check cache first (instant retrieval for cached repos)
  2. Fetch README and repository structure (selective tree exploration)
  3. Identify manifest files (package.json, requirements.txt, etc.)
  4. Scan for entry points and tech stack
  5. Sample important code files with concurrent I/O
  6. Ask LLM if additional files are needed (agentic feedback)
  7. Generate comprehensive summary
  8. Store result in local SQLite cache for future requests

Optimization Features:
  ✓ Caching Layer: Instant retrieval for repeated URLs (summary_cache.db)
  ✓ Concurrent I/O: Parallel file fetching with ThreadPoolExecutor
  ✓ Smart Filtering: Removes 15-20% noise (URLs, badges, boilerplate)
  ✓ Selective Tree: Only fetches hot directories (src, app, lib, etc.)
  ✓ Token Budget: Dynamic allocation based on repo type

Output includes execution time, token usage, and estimated cost.
Smart optimization ensures minimal API calls and token usage.
Cache eliminates redundant API queries and LLM costs for repeated requests.
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    repo_url = sys.argv[1]
    
    # Validate URL format
    if not repo_url.startswith("https://github.com/"):
        print(f"\n[ERROR] Invalid URL: {repo_url}")
        print(f"  Expected: https://github.com/owner/repo")
        print_usage()
        sys.exit(1)
    
    success = run_summary(repo_url)
    sys.exit(0 if success else 1)
