# GitHub Repository Summarizer

**Personal ID:** 641463731438  
**Course:** Nebuis AI Performance Engineering Course

---

## Project Overview

This project provides an intelligent GitHub repository summarizer that uses Claude AI to generate comprehensive summaries of any public GitHub repository. The system automatically analyzes repository structure, code files, documentation, and technology stack to produce meaningful summaries while optimizing token usage and API costs.

## Key Features

### 1. **Dynamic Repository Type Detection**
- Automatically classifies repositories as **Code-Heavy** or **Content-Heavy**
- Code-Heavy: Repositories with `.py`, `.js`, `.ts`, `.java`, etc.
- Content-Heavy: Documentation repositories, quiz collections, educational content
- Adjusts analysis strategy based on repository type for optimal token usage

### 2. **Adaptive Token Budgeting**
- **For Content Repositories:** Allocates 5,000 tokens for README (up from 400)
  - Captures full table of contents and comprehensive documentation
  - Example: LinkedIn skill assessments quiz repository
- **For Code Repositories:** Allocates 800 tokens for README, 1,500 for source code
  - Focuses on actual implementation details
  - Example: Flask, Django, requests libraries

### 3. **Static Code Analysis Integration**
- Analyzes file extensions and manifest files to detect:
  - Programming languages (Python, JavaScript, TypeScript, Go, Java, etc.)
  - Framework detection (React, Django, Express, etc.)
  - Technology stack composition
- Filters out unnecessary directories (node_modules, .git, __pycache__, etc.)
- Prioritizes entry points (app.py, main.py, index.js, server.js)

### 4. **Fully Functional Agentic Loop (Phase 4)**
- **Phase 1:** Fetches README and repository structure
- **Phase 2:** Identifies manifest files and technology stack
- **Phase 3:** Samples important code files
- **Phase 4 (Agentic):** 
  - Asks Claude: "Which 2 files are most critical for a deep dive?"
  - Fetches those specific files from GitHub
  - Re-summarizes with detailed analysis

### 5. **Optimized Orchestration**
- Parallel fetching using ThreadPoolExecutor (2 workers max)
- Smart URL resolution (raw.githubusercontent.com for content, api.github.com for metadata)
- Fallback branch handling (main → master)
- Efficient token tracking and cost estimation

---

## Installation

### Requirements
- Python 3.8+
- ANTHROPIC_API_KEY (get from [console.anthropic.com](https://console.anthropic.com))
- GitHub access (public repositories)

### Setup

```bash
# Clone or navigate to the project directory
cd github-summarizer

# Install dependencies
pip install -r requirements.txt

# Set your API key (Windows PowerShell)
$env:ANTHROPIC_API_KEY = "your-api-key-here"

# Or create a .env file
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

---

## Usage

### Basic Command

```bash
python run_summarizer.py <GitHub-URL>
```

### Examples

```bash
# Summarize Flask repository
python run_summarizer.py https://github.com/pallets/flask

# Summarize Requests library
python run_summarizer.py https://github.com/psf/requests

# Summarize LinkedIn quiz repository (Content-Heavy)
python run_summarizer.py https://github.com/Ebazhanov/linkedin-skill-assessments-quizzes

# Summarize FiveThirtyEight data (Content-Heavy)
python run_summarizer.py https://github.com/fivethirtyeight/data
```

### Output

The script provides:
- **Execution Time:** Total seconds to analyze and summarize
- **Token Usage:** Input and output tokens consumed
- **Estimated Cost:** API cost based on token usage
- **Summary:** Comprehensive repository analysis with:
  - Purpose and main features
  - Technology stack
  - Key code structure
  - Notable patterns and design

---

## How It Works

### Flow Diagram

```
GitHub URL
    ↓
[URL Validation & Parsing]
    ↓
[Parallel Fetch: README + Tree Structure]
    ↓
[Repository Type Detection]
    ├─→ Code-Heavy: Focus on source code samples
    └─→ Content-Heavy: Focus on README and documentation
    ↓
[Extract Tech Stack & Language Detection]
    ↓
[Dynamic Budget Allocation]
    ├─→ README Budget (800 or 5000 tokens)
    └─→ Code Budget (1500 or 200 tokens)
    ↓
[Sample Important Code Files]
    ├─→ Prioritize entry points
    ├─→ Use raw GitHub URLs
    └─→ Truncate to token budget
    ↓
[Initial Claude Summary]
    ↓
[Agentic Loop: Ask for Missing Files]
    ├─→ Claude identifies 2 critical files
    ├─→ Fetch from GitHub
    └─→ Re-analyze with new context
    ↓
[Final Comprehensive Summary]
    ↓
[Display Results + Token Usage]
```

---

## Optimization Strategies

### Token Efficiency
- **Sentence-aware truncation:** Preserves context by truncating at sentence boundaries
- **Dynamic allocation:** Content repos get more README tokens, code repos get more code tokens
- **Selective sampling:** Only 3-5 important files per repository
- **Parallel operations:** Reduces wall-clock time even with token limits

### API Efficiency
- **Batch requests:** Parallel fetching of README and tree structure
- **Smart fallbacks:** Branch resolution (main → master)
- **Timeout handling:** 5-second timeouts prevent hanging
- **Error recovery:** Gracefully skips unavailable files

### Cost Estimation
```
Input Tokens (based on file size) = words × 1.3
Output Tokens (from Claude) = tracked from API response
Cost = (input_tokens + output_tokens) / 1000 × $0.08
```

---

## Configuration

### Token Budgets (Adjustable)
Edit in `github_client.py`:
```python
readme_budget = 5000 if is_content_repo else 800
code_budget = 200 if is_content_repo else 1500
```

### Excluded Directories
```python
self.exclude_dirs = {
    '.git', 'node_modules', 'dist', 'build', 
    '__pycache__', '.venv', 'venv', '.next', 
    'target', 'coverage'
}
```

### Supported Code Extensions
```python
self.code_extensions = [
    '.py', '.js', '.ts', '.java', '.cpp', 
    '.c', '.go', '.rb', '.php', '.scala', '.rs', '.cs'
]
```

---

## Example Output

```
======================================================================
               GITHUB REPOSITORY SUMMARIZER (OPTIMIZED)
======================================================================

Repository: https://github.com/pallets/flask
Time: 2026-03-06 15:38:08

Analyzing: pallets/flask

[Phase 1] Fetching initial context and manifests...
  [OK] README size: 1639 chars
  [OK] Code files sampled: 3
  [OK] Tech stack identified: Python

[Phase 2] Generating summary with Claude Haiku...

[Phase 4] Agentic Deep-Dive Loop...
  [OK] Claude identified important files
  [OK] Fetched and re-analyzed

Summary:
--------
Flask is a lightweight Python web framework designed for building 
web applications with minimal boilerplate. It emphasizes flexibility 
and extensibility through its modular design...

Token Usage:
  Input Tokens: 1,247
  Output Tokens: 856
  Total: 2,103
  Estimated Cost: $0.17

Execution Time: 8.4 seconds
```

---

## Troubleshooting

### Issue: "Could not resolve authentication method"
**Solution:** Set `ANTHROPIC_API_KEY` environment variable
```bash
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

### Issue: "README size: 0 chars"
**Solution:** Repository may not have README.md. Check repository manually.

### Issue: "Code files sampled: 0"
**Solution:** 
- May be a content-only repository (detected correctly)
- Check if code files exist in main/master branch

### Issue: "Invalid GitHub URL"
**Solution:** Use full GitHub URL format: `https://github.com/owner/repo`

---

## Performance Metrics

### Benchmarks (Tested Repositories)

| Repository | Type | Execution Time | Token Usage | Cost |
|------------|------|-----------------|-------------|------|
| pallets/flask | Code | 8.4s | 2,103 | $0.17 |
| psf/requests | Code | 7.2s | 1,895 | $0.15 |
| Ebazhanov/linkedin-quizzes | Content | 5.1s | 4,247 | $0.34 |
| fivethirtyeight/data | Content | 6.3s | 3,891 | $0.31 |

---

## Technologies Used

- **Claude Haiku 4.5** - LLM for intelligent summarization
- **Anthropic SDK** - API integration
- **ThreadPoolExecutor** - Parallel API requests
- **Requests** - HTTP client for GitHub API
- **Python 3.8+** - Core language

---

## Limitations

- Only works with public GitHub repositories
- Large repositories (10K+ files) may timeout
- Binary files are skipped
- Rate-limited by GitHub API (60 req/hour without auth)
- Non-code content (images, videos) are ignored

---

## Future Enhancements

- [ ] Private repository support (with GitHub token)
- [ ] Multi-language analysis (detect non-code files)
- [ ] Dependency graph visualization
- [ ] Historical trend analysis
- [ ] Custom prompt templates
- [ ] Output formatting (HTML, JSON, PDF)

---

## Course Information

**Student ID:** 641463731438  
**Course:** Nebuis AI Performance Engineering  
**Topic:** Token Optimization & Agentic AI Architecture

---

## License

MIT License - Feel free to use and modify for educational purposes.

---

## Contact & Support

For issues or questions about this project, refer to the attached documentation files:
- `QUICK_START.md` - Quick setup guide
- `QUICK_CLI_REFERENCE.md` - Command reference
- `OPTIMIZATION_DOCUMENTATION.md` - Detailed optimization strategies
- `DEPLOYMENT_CHECKLIST.md` - Production deployment guide

---

**Last Updated:** March 6, 2026
