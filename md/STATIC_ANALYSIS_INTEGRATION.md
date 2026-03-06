"""
Integration Guide: Adding Static Code Analysis to Summarizer

This shows how to enhance your existing summarizer with code quality metrics
"""

# Option 1: Add to run_summarizer.py (in the run_summary function)
# ================================================================

def run_summary_with_analysis(repo_url):
    """Enhanced version with static code analysis"""
    from static_analyzer import StaticCodeAnalyzer
    
    # ... existing code ...
    
    # After fetching repository data
    repo_data = gh_client.get_repo_summary(repo_url)
    
    # NEW: Analyze code quality
    analyzer = StaticCodeAnalyzer()
    code_analysis = analyzer.analyze_code_files(repo_data['code_files'])
    
    print_section("STEP 1.5: Static Code Analysis")
    print(f"✓ Analysis completed")
    print(f"  - Languages: {', '.join(code_analysis['languages'])}")
    print(f"  - Total Lines: {code_analysis['total_lines']}")
    print(f"  - Functions: {code_analysis['total_functions']}")
    print(f"  - Classes: {code_analysis['total_classes']}")
    print(f"  - Complexity Score: {code_analysis['complexity_score']:.1f}")
    
    if code_analysis['quality_issues']:
        print(f"\n  Quality Issues:")
        for issue in code_analysis['quality_issues'][:3]:
            print(f"    {issue}")
    
    # ... rest of existing code ...


# Option 2: Add to LLM prompt (enhanced Q4 answer)
# ================================================

def enhanced_prompt_with_analysis(repo_data, code_analysis):
    """Add code analysis insights to the summary prompt"""
    
    languages = ', '.join(code_analysis['languages']) or 'Unknown'
    complexity = code_analysis['complexity_score']
    issues = len(code_analysis['quality_issues'])
    
    analysis_context = f"""
Additional Code Quality Metrics:
- Programming Languages: {languages}
- Code Complexity Score: {complexity:.1f}/10
- Quality Issues Found: {issues}
- Total Functions: {code_analysis['total_functions']}
- Total Classes: {code_analysis['total_classes']}
- Total Lines of Code: {code_analysis['total_lines']}
"""
    
    return analysis_context


# Option 3: Add to LLM Client (new function)
# ===========================================

def get_code_quality_section(code_files):
    """New function for llm_client.py"""
    from static_analyzer import StaticCodeAnalyzer, estimate_code_quality
    
    analyzer = StaticCodeAnalyzer()
    analysis = analyzer.analyze_code_files(code_files)
    quality_score = estimate_code_quality(code_files)
    
    quality_section = f"""
Q4: CODE QUALITY ASSESSMENT
Overall Quality Score: {quality_score:.0%}
Languages Used: {', '.join(analysis['languages']) or 'N/A'}
Code Complexity: {analysis['complexity_score']:.1f}/10
Total Functions: {analysis['total_functions']}
Total Classes: {analysis['total_classes']}
Documentation Coverage: Est. {sum(m.get('documentation', 0) for m in analysis['metrics'].values()) / len(analysis['metrics']) * 100:.0f}%

Quality Issues Found:
{chr(10).join('- ' + issue for issue in analysis['quality_issues'][:5]) if analysis['quality_issues'] else '- No major issues detected'}
"""
    
    return quality_section


# Full Integration Example
# ========================

STATIC_ANALYZER_INTEGRATION = """

# In llm_client.py - modify summarize() method:

def summarize(self, repo_data):
    '''Generate summary with code quality insights'''
    from static_analyzer import StaticCodeAnalyzer
    
    # Existing code...
    structure = repo_data['structure']
    readme_text = repo_data['readme']
    code_files_list = repo_data['code_files']
    
    # NEW: Get static analysis
    analyzer = StaticCodeAnalyzer()
    code_analysis = analyzer.analyze_code_files(code_files_list)
    languages = ', '.join(code_analysis['languages']) or 'Unknown'
    complexity = f"{code_analysis['complexity_score']:.1f}"
    
    # Modified prompt with analysis
    user_prompt = f'''
Q1: PURPOSE
What is the main purpose of this project?

Q2: ARCHITECTURE  
Describe the key components and how they interact

Q3: KEY FEATURES
List the main functionality and features

Q4: CODE QUALITY & METADATA
- Programming Languages: {languages}
- Code Complexity: {complexity}/10 (1=simple, 10=complex)
- Functions: {code_analysis['total_functions']}
- Classes: {code_analysis['total_classes']}
- Quality Issues: {len(code_analysis['quality_issues'])}
Based on this analysis, assess the code quality.
'''
    
    # ... rest of existing code ...


# In run_summarizer.py - add after Step 1:

    print_section("STEP 1.5: Code Quality Analysis")
    
    analyzer = StaticCodeAnalyzer()
    code_analysis = analyzer.analyze_code_files(repo_data['code_files'])
    
    print(f"✓ {len(code_analysis['languages'])} languages detected")
    print(f"  - Languages: {', '.join(code_analysis['languages'])}")
    print(f"  - {code_analysis['total_functions']} functions, {code_analysis['total_classes']} classes")
    print(f"  - Complexity Score: {code_analysis['complexity_score']:.1f}/10")
    print(f"  - Quality Issues: {len(code_analysis['quality_issues'])}")
"""

print(STATIC_ANALYZER_INTEGRATION)
