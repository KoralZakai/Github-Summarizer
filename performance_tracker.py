"""
Performance tracking for GitHub repository summarization
Tracks metrics like latency, token usage, and cost
"""

import json
import os
from datetime import datetime
from pathlib import Path


class PerformanceTracker:
    """Track and store performance metrics for summarization runs"""
    
    def __init__(self, metrics_file="metrics.json"):
        """
        Initialize the performance tracker
        
        Args:
            metrics_file: Path to JSON file for storing metrics
        """
        self.metrics_file = metrics_file
        self.metrics = []
        self.load_metrics()
    
    def load_metrics(self):
        """Load existing metrics from file if it exists"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    self.metrics = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.metrics = []
        else:
            self.metrics = []
    
    def save_metrics(self):
        """Save metrics to JSON file"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save metrics to {self.metrics_file}: {e}")
    
    def track_summary(self, repo_name, model, response, latency_ms, input_tokens, output_tokens):
        """
        Track a summarization run
        
        Args:
            repo_name: Name of the repository
            model: Model used for summarization
            response: The generated summary text
            latency_ms: Latency in milliseconds
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
        
        Returns:
            dict: Metric record with all tracking information
        """
        # Calculate cost (Haiku pricing: $0.80/1M input tokens, $2.40/1M output tokens)
        input_cost = (input_tokens * 0.80) / 1_000_000
        output_cost = (output_tokens * 2.40) / 1_000_000
        total_cost = input_cost + output_cost
        
        # Calculate tokens per second
        tokens_per_second = (input_tokens + output_tokens) / (latency_ms / 1000) if latency_ms > 0 else 0
        
        # Create metric record
        metric = {
            'timestamp': datetime.now().isoformat(),
            'repo_name': repo_name,
            'model': model,
            'latency_ms': latency_ms,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost_usd': round(total_cost, 6),
            'tokens_per_second': round(tokens_per_second, 2),
            'response_length': len(response) if response else 0,
        }
        
        # Add to metrics list and save
        self.metrics.append(metric)
        self.save_metrics()
        
        return metric
    
    def get_metrics(self):
        """Get all tracked metrics"""
        return self.metrics
    
    def get_summary_stats(self):
        """Get summary statistics of all tracked runs"""
        if not self.metrics:
            return None
        
        total_runs = len(self.metrics)
        total_tokens = sum(m.get('total_tokens', 0) for m in self.metrics)
        total_cost = sum(m.get('cost_usd', 0) for m in self.metrics)
        avg_latency = sum(m.get('latency_ms', 0) for m in self.metrics) / total_runs if total_runs > 0 else 0
        total_latency = sum(m.get('latency_ms', 0) for m in self.metrics)
        
        return {
            'total_runs': total_runs,
            'total_tokens': total_tokens,
            'total_cost_usd': round(total_cost, 6),
            'avg_latency_ms': round(avg_latency, 2),
            'total_latency_ms': round(total_latency, 2),
            'unique_repos': len(set(m.get('repo_name', '') for m in self.metrics)),
            'unique_models': list(set(m.get('model', '') for m in self.metrics if m.get('model'))),
        }
