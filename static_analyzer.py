"""
Static Code Analysis Module for GitHub Repository Summarizer

Analyzes code files statically (without running them) to extract:
- Code complexity metrics (cyclomatic complexity, lines of code)
- Code quality issues (code smell patterns)
- Language detection
- Code patterns and structure
- Performance concerns
"""

import re
from typing import Dict, List

class StaticCodeAnalyzer:
    """Analyze code structure and quality without execution"""
    
    def __init__(self):
        self.language_patterns = {
            '.py': {'name': 'Python', 'comment': '#', 'keywords': ['def', 'class', 'import']},
            '.js': {'name': 'JavaScript', 'comment': '//', 'keywords': ['function', 'class', 'const']},
            '.ts': {'name': 'TypeScript', 'comment': '//', 'keywords': ['function', 'class', 'interface']},
            '.java': {'name': 'Java', 'comment': '//', 'keywords': ['class', 'public', 'import']},
            '.cpp': {'name': 'C++', 'comment': '//', 'keywords': ['class', 'void', 'int']},
            '.c': {'name': 'C', 'comment': '//', 'keywords': ['int', 'void', 'struct']},
            '.go': {'name': 'Go', 'comment': '//', 'keywords': ['func', 'type', 'package']},
            '.rb': {'name': 'Ruby', 'comment': '#', 'keywords': ['def', 'class', 'require']},
            '.php': {'name': 'PHP', 'comment': '//', 'keywords': ['function', 'class', 'public']},
            '.rs': {'name': 'Rust', 'comment': '//', 'keywords': ['fn', 'struct', 'impl']},
            '.yml': {'name': 'YAML', 'comment': '#', 'keywords': []},
            '.yaml': {'name': 'YAML', 'comment': '#', 'keywords': []},
        }
    
    def analyze_code_files(self, code_files: List[Dict]) -> Dict:
        """Analyze a list of code files"""
        analysis = {
            'languages': set(),
            'total_lines': 0,
            'total_functions': 0,
            'total_classes': 0,
            'complexity_score': 0,
            'quality_issues': [],
            'metrics': {}
        }
        
        for file in code_files:
            if not isinstance(file, dict):
                continue
            
            path = file.get('path', '')
            content = file.get('content', '')
            
            if not content or not path:
                continue
            
            file_analysis = self.analyze_file(path, content)
            
            # Aggregate
            if file_analysis.get('language'):
                analysis['languages'].add(file_analysis['language'])
            
            analysis['total_lines'] += file_analysis.get('lines_of_code', 0)
            analysis['total_functions'] += file_analysis.get('functions', 0)
            analysis['total_classes'] += file_analysis.get('classes', 0)
            analysis['complexity_score'] += file_analysis.get('complexity', 0)
            analysis['quality_issues'].extend(file_analysis.get('issues', []))
            analysis['metrics'][path] = file_analysis
        
        # Convert set to list
        analysis['languages'] = list(analysis['languages'])
        
        return analysis
    
    def analyze_file(self, filepath: str, content: str) -> Dict:
        """Analyze a single code file"""
        # Detect language
        ext = None
        for k in self.language_patterns.keys():
            if filepath.endswith(k):
                ext = k
                break
        
        if not ext:
            return {'language': 'unknown'}
        
        lang_info = self.language_patterns[ext]
        
        analysis = {
            'language': lang_info['name'],
            'file': filepath,
            'lines_of_code': len(content.split('\n')),
            'functions': self._count_functions(content, lang_info),
            'classes': self._count_classes(content, lang_info),
            'complexity': self._estimate_complexity(content),
            'issues': self._detect_issues(content, lang_info),
            'documentation': self._estimate_documentation(content, lang_info),
        }
        
        return analysis
    
    def _count_functions(self, content: str, lang_info: Dict) -> int:
        """Count function definitions"""
        count = 0
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            # Skip comments
            if line.startswith(lang_info['comment']):
                continue
            
            # Look for function keywords
            if 'def ' in line and '(' in line:  # Python
                count += 1
            elif 'function ' in line and '(' in line:  # JavaScript/PHP
                count += 1
            elif re.match(r'^\s*(public|private|protected)?\s+\w+\s+\w+\s*\(', line):  # Java/C++
                count += 1
            elif 'fn ' in line and '(' in line:  # Rust
                count += 1
        
        return count
    
    def _count_classes(self, content: str, lang_info: Dict) -> int:
        """Count class definitions"""
        count = 0
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            # Skip comments
            if line.startswith(lang_info['comment']):
                continue
            
            # Look for class keywords
            if line.startswith('class ') and '(' in line:
                count += 1
            elif line.startswith('class ') and ':' in line:
                count += 1
            elif re.match(r'(public|private)?\s+class\s+\w+', line):
                count += 1
            elif line.startswith('type ') and '{' in line:  # Go/Rust
                count += 1
        
        return count
    
    def _estimate_complexity(self, content: str) -> float:
        """Estimate cyclomatic complexity"""
        complexity = 1.0  # Base complexity
        
        # Count control flow statements
        keywords = ['if ', ' else', 'elif ', 'for ', 'while ', 'switch ', 'case ', 'try ', 'except ', 'catch ']
        
        for keyword in keywords:
            complexity += content.count(keyword) * 0.5
        
        # Nested structures increase complexity
        nesting_depth = max(len(line) - len(line.lstrip()) for line in content.split('\n'))
        complexity += (nesting_depth // 4) * 0.3
        
        return round(complexity, 2)
    
    def _detect_issues(self, content: str, lang_info: Dict) -> List[str]:
        """Detect potential code quality issues"""
        issues = []
        
        # Check for long lines (>100 chars typically indicates readability issue)
        long_lines = [line for line in content.split('\n') if len(line) > 120]
        if long_lines:
            issues.append(f"⚠️ {len(long_lines)} lines exceed 120 characters (readability concern)")
        
        # Check for deeply nested code
        max_indent = max(len(line) - len(line.lstrip()) for line in content.split('\n'))
        if max_indent > 32:  # 8+ levels of indentation
            issues.append(f"⚠️ Deep nesting detected (~{max_indent//4} levels) - consider refactoring")
        
        # Check for unused imports (Python/JavaScript specific)
        if lang_info['name'] in ['Python', 'JavaScript']:
            imports = re.findall(r'(import|require)\s+(\w+)', content)
            for imp_type, module in imports:
                if module not in content[content.find(imp_type):]:
                    issues.append(f"⚠️ Potentially unused import: {module}")
        
        # Check for magic numbers
        magic_numbers = re.findall(r'[^a-zA-Z0-9_](10|100|255|1000|3600)\b', content)
        if magic_numbers and len(magic_numbers) > 3:
            issues.append(f"⚠️ Multiple magic numbers found - use named constants")
        
        # Check for TODO/FIXME comments
        todos = len(re.findall(r'(TODO|FIXME|HACK|XXX)', content))
        if todos > 0:
            issues.append(f"ℹ️ {todos} TODO/FIXME comments found")
        
        # Check for error handling
        try_blocks = content.count('try')
        if try_blocks == 0 and lang_info['name'] in ['Python', 'JavaScript', 'Java']:
            issues.append(f"⚠️ No error handling detected - add try/except blocks")
        
        return issues
    
    def _estimate_documentation(self, content: str, lang_info: Dict) -> float:
        """Estimate documentation coverage (0-1)"""
        total_lines = len(content.split('\n'))
        
        # Count comment lines
        comment_count = 0
        for line in content.split('\n'):
            if lang_info['comment'] in line:
                comment_count += 1
        
        # Docstrings/javadoc
        docstring_count = len(re.findall(r'("""|\'\'\')|(/**|/*)', content))
        
        documentation_score = (comment_count + docstring_count * 5) / total_lines
        return min(1.0, round(documentation_score, 2))
    
    def get_summary(self, analysis: Dict) -> str:
        """Generate human-readable summary of analysis"""
        summary = []
        
        summary.append(f"🔍 Code Analysis Summary:")
        summary.append(f"  Languages: {', '.join(analysis['languages']) if analysis['languages'] else 'None detected'}")
        summary.append(f"  Total Lines: {analysis['total_lines']}")
        summary.append(f"  Functions: {analysis['total_functions']}")
        summary.append(f"  Classes: {analysis['total_classes']}")
        summary.append(f"  Complexity Score: {analysis['complexity_score']:.1f} (higher = more complex)")
        
        if analysis['quality_issues']:
            summary.append(f"\n⚠️ Quality Issues Found:")
            for issue in analysis['quality_issues'][:5]:  # Show top 5
                summary.append(f"  {issue}")
            if len(analysis['quality_issues']) > 5:
                summary.append(f"  ... and {len(analysis['quality_issues']) - 5} more")
        else:
            summary.append(f"\n✅ No major quality issues detected")
        
        return "\n".join(summary)


# Convenience functions
def detect_languages(code_files: List[Dict]) -> List[str]:
    """Quick language detection from code files"""
    analyzer = StaticCodeAnalyzer()
    analysis = analyzer.analyze_code_files(code_files)
    return analysis['languages']


def estimate_code_quality(code_files: List[Dict]) -> float:
    """Quick quality score (0-1, higher is better)"""
    analyzer = StaticCodeAnalyzer()
    analysis = analyzer.analyze_code_files(code_files)
    
    # Calculate quality score
    base_score = 1.0
    base_score -= len(analysis['quality_issues']) * 0.1  # Deduct for issues
    base_score -= (analysis['complexity_score'] / 10) * 0.05  # Deduct for complexity
    
    # Bonus for documentation
    if 'metrics' in analysis:
        docs = [m.get('documentation', 0) for m in analysis['metrics'].values()]
        if docs:
            avg_doc = sum(docs) / len(docs)
            base_score += avg_doc * 0.1
    
    return max(0.0, min(1.0, round(base_score, 2)))


if __name__ == "__main__":
    # Example usage
    test_code = '''
def calculate_sum(numbers):
    """Calculate sum of numbers"""
    total = 0
    for num in numbers:
        if num > 0:
            total += num
        else:
            if num < -100:
                total -= num * 2
            else:
                total -= num
    return total

class Calculator:
    def add(self, a, b):
        return a + b
    
    def multiply(self, a, b):
        result = 0
        for i in range(a):
            result += b
        return result
    '''
    
    analyzer = StaticCodeAnalyzer()
    analysis = analyzer.analyze_file('test.py', test_code)
    
    print("Analysis Results:")
    print(f"Language: {analysis['language']}")
    print(f"Lines of Code: {analysis['lines_of_code']}")
    print(f"Functions: {analysis['functions']}")
    print(f"Classes: {analysis['classes']}")
    print(f"Complexity: {analysis['complexity']}")
    print(f"Issues: {analysis['issues']}")
    print(f"Documentation: {analysis['documentation']:.0%}")
