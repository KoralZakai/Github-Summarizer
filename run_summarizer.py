#!/usr/bin/env python3
"""
Simple CLI for testing GitHub repository summaries
Shows: execution time, token counts, cost, and quality metrics

Usage:
    python run_summarizer.py https://github.com/owner/repo
    python run_summarizer.py https://github.com/pallets/flask
"""

import sys
import time
import json
from datetime import datetime
from github_client import GitHubClient
from llm_client import LLMClient
from performance_tracker import PerformanceTracker

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(text.center(70))
    print("="*70)

def print_section(title):
    """Print formatted section"""
    print(f"\n📊 {title}")
    print("-" * 70)

def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token"""
    if text is None:
        return 0
    # If it's already a number (char count), use it directly
    if isinstance(text, int):
        return text // 4
    # Otherwise treat as string and count chars
    text_str = str(text) if not isinstance(text, str) else text
    return len(text_str) // 4

def run_summary(repo_url):
    """Run summarization with timing and metrics"""
    
    print_header("🚀 GITHUB REPOSITORY SUMMARIZER")
    print(f"\nRepository: {repo_url}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    gh_client = GitHubClient()
    llm_client = LLMClient()
    tracker = PerformanceTracker()
    
    try:
        # Step 1: Fetch repository data
        print_section("STEP 1: Fetching Repository Data")
        start_fetch = time.time()
        
        repo_data = gh_client.get_repo_data(repo_url)
        
        fetch_time = time.time() - start_fetch
        
        # Safely get values with type checking
        structure = repo_data.get('structure', '')
        readme = repo_data.get('readme', '')
        code_files = repo_data.get('code_files', [])
        
        # Ensure they're the right types
        if structure is None:
            structure = ''
        if readme is None:
            readme = ''
        if code_files is None:
            code_files = []
        
        structure_size = len(str(structure)) if structure else 0
        readme_size = len(str(readme)) if readme else 0
        
        # Calculate total characters for fetch
        code_files_size = sum(len(str(f.get('content', '')) if isinstance(f, dict) else '') for f in code_files)
        fetch_total_chars = structure_size + readme_size + code_files_size
        fetch_tokens = estimate_tokens(fetch_total_chars)
        
        print(f"✓ Fetch completed in {fetch_time:.2f}s")
        print(f"  - Structure: {len(str(structure).split(chr(10)))} lines, {structure_size} chars")
        print(f"  - README: {readme_size} characters")
        print(f"  - Code files found: {len(code_files)}")
        for i, f in enumerate(code_files, 1):
            file_path = f.get('path', 'unknown') if isinstance(f, dict) else str(f)
            file_content = f.get('content', '') if isinstance(f, dict) else ''
            file_size = len(str(file_content)) if file_content else 0
            print(f"    {i}. {file_path:<40} ({file_size} chars)")
        print(f"  - Estimated tokens (fetch): ~{fetch_tokens}")
        
        # Step 2: Generate summary
        print_section("STEP 2: Generating Summary")
        start_summary = time.time()
        
        summary = llm_client.summarize(repo_data)
        
        summary_time = time.time() - start_summary
        
        # Estimate tokens with proper type handling
        summary_str = str(summary) if summary else ""
        
        # Recalculate input tokens (same as fetch)
        structure = repo_data.get('structure', '') or ''
        readme = repo_data.get('readme', '') or ''
        code_files_list = repo_data.get('code_files', []) or []
        
        structure_chars = len(str(structure))
        readme_chars = len(str(readme))
        code_chars = sum(len(str(f.get('content', '') if isinstance(f, dict) else '')) for f in code_files_list)
        input_chars = structure_chars + readme_chars + code_chars
        
        output_chars = len(summary_str)
        
        input_tokens = estimate_tokens(input_chars)
        output_tokens = estimate_tokens(output_chars)
        total_tokens = input_tokens + output_tokens
        
        print(f"✓ Summary generated in {summary_time:.2f}s")
        print(f"  - Estimated input tokens: ~{input_tokens}")
        print(f"  - Estimated output tokens: ~{output_tokens}")
        print(f"  - Total estimated tokens: ~{total_tokens}")
        
        # Calculate cost (Haiku pricing)
        estimated_cost = (input_tokens * 0.80 + output_tokens * 2.40) / 1_000_000
        print(f"  - Estimated cost: ${estimated_cost:.6f}")
        
        # Step 3: Display summary
        print_section("STEP 3: Generated Summary")
        print(summary)
        
        # Step 4: Performance metrics
        print_section("STEP 4: Performance Metrics")
        
        total_time = fetch_time + summary_time
        
        print(f"⏱️  Execution Timeline:")
        print(f"  - Fetch time: {fetch_time:.3f}s ({fetch_time/total_time*100:.1f}%)")
        print(f"  - Summary time: {summary_time:.3f}s ({summary_time/total_time*100:.1f}%)")
        print(f"  - Total time: {total_time:.3f}s")
        
        print(f"\n📈 Token Summary:")
        print(f"  - Input tokens: ~{input_tokens}")
        print(f"  - Output tokens: ~{output_tokens}")
        print(f"  - Total tokens: ~{total_tokens}")
        print(f"  - Cost: ${estimated_cost:.6f}")
        
        # Quality check
        quality_score = 0
        required_sections = ['Q1:', 'Q2:', 'Q3:', 'Q4:']
        for section in required_sections:
            if section in summary:
                quality_score += 0.25
        
        print(f"\n✓ Quality Metrics:")
        print(f"  - Completeness: {quality_score:.0%} ({int(quality_score*4)}/4 sections)")
        print(f"  - All answers present: {'Yes ✅' if quality_score == 1.0 else 'No ⚠️'}")
        
        # Step 5: Save to tracker
        print_section("STEP 5: Saving Metrics")
        from llm_client import select_model
        model = select_model(repo_data)
        
        metric = tracker.track_summary(
            repo_name=repo_url.split('/')[-1],
            model=model,
            response=summary,
            latency_ms=summary_time * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        
        print(f"✓ Metrics saved to tracker")
        print(f"  - Model selected: {model}")
        print(f"  - Repository: {metric['repo_name']}")
        
        # Final summary
        print_section("FINAL SUMMARY")
        print(f"Total Execution Time:    {total_time:.3f} seconds")
        print(f"Total Tokens Used:       {total_tokens} tokens")
        print(f"Estimated Cost:          ${estimated_cost:.6f}")
        print(f"Quality Score:           {quality_score:.0%}")
        print(f"Selected Model:          {model}")
        print(f"Timestamp:               {datetime.now().isoformat()}")
        
        print("\n✅ SUCCESS - Summary generated and metrics tracked")
        print("="*70 + "\n")
        
        return True
        
    except ValueError as e:
        print(f"\n❌ ERROR: Invalid GitHub URL")
        print(f"   Error: {str(e)}")
        print(f"\n   Expected format: https://github.com/owner/repo")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print(f"\n   Check:")
        print(f"   - GitHub URL is valid and public")
        print(f"   - ANTHROPIC_API_KEY is set in .env")
        print(f"   - GITHUB_TOKEN is set in .env (optional)")
        print(f"   - Internet connection is working")
        return False

def print_usage():
    """Print usage instructions"""
    print_header("USAGE")
    print("""
Examples:
    python run_summarizer.py https://github.com/pallets/flask
    python run_summarizer.py https://github.com/tornadoweb/tornado
    python run_summarizer.py https://github.com/psf/requests

The script will:
  1. Fetch repository data from GitHub
  2. Generate AI summary
  3. Show timing and token metrics
  4. Display quality scores

Output includes:
  - ⏱️  Execution time breakdown
  - 📈 Token usage and cost
  - ✓ Quality metrics
  - 📊 Model selection info
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    repo_url = sys.argv[1]
    
    # Validate URL format
    if not repo_url.startswith("https://github.com/"):
        print(f"\n❌ Invalid URL: {repo_url}")
        print(f"   Expected: https://github.com/owner/repo")
        print_usage()
        sys.exit(1)
    
    success = run_summary(repo_url)
    sys.exit(0 if success else 1)
