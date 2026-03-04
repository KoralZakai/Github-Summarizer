import time
import json
from datetime import datetime
from typing import Dict, List, Optional

class PerformanceTracker:
    """Track and analyze LLM performance metrics for optimization evaluation"""
    
    def __init__(self):
        self.metrics: List[Dict] = []
    
    def track_summary(self, repo_name: str, model: str, response, latency_ms: float, input_tokens: int, output_tokens: int) -> Dict:
        """Track a single summary generation"""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "repo_name": repo_name,
            "model": model,
            
            # Latency Metrics
            "latency_ms": latency_ms,
            
            # Token & Cost Metrics
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost_usd": self._calculate_cost(model, input_tokens, output_tokens),
            
            # Quality Metrics
            "answer_completeness": self._score_completeness(response),
            "has_all_four_questions": "Q1:" in response and "Q2:" in response and "Q3:" in response and "Q4:" in response,
        }
        self.metrics.append(metric)
        return metric
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on model pricing"""
        pricing = {
            "claude-haiku-4-5": {"input": 0.80, "output": 2.40},
            "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
            "claude-opus-4-1-20250805": {"input": 15.00, "output": 75.00},
        }
        
        if model not in pricing:
            model = "claude-haiku-4-5"
        
        rates = pricing[model]
        cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
        return round(cost, 6)
    
    def _score_completeness(self, response: str) -> float:
        """Score 0-1 based on how many questions are answered"""
        questions_answered = 0
        for i in range(1, 5):
            if f"Q{i}:" in response:
                questions_answered += 1
        return questions_answered / 4
    
    def get_optimization_report(self) -> Dict:
        """Generate comprehensive optimization report"""
        if not self.metrics:
            return {"error": "No metrics collected yet"}
        
        total_tests = len(self.metrics)
        
        # Aggregate metrics by model
        model_stats = {}
        for metric in self.metrics:
            model = metric["model"]
            if model not in model_stats:
                model_stats[model] = {
                    "count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "total_latency": 0.0,
                    "avg_completeness": 0.0,
                    "complete_answers": 0,
                }
            
            ms = model_stats[model]
            ms["count"] += 1
            ms["total_tokens"] += metric["total_tokens"]
            ms["total_cost"] += metric["estimated_cost_usd"]
            ms["total_latency"] += metric["latency_ms"]
            ms["avg_completeness"] += metric["answer_completeness"]
            if metric["has_all_four_questions"]:
                ms["complete_answers"] += 1
        
        # Calculate averages
        for model in model_stats:
            ms = model_stats[model]
            ms["avg_tokens"] = ms["total_tokens"] / ms["count"]
            ms["avg_cost"] = ms["total_cost"] / ms["count"]
            ms["avg_latency_ms"] = ms["total_latency"] / ms["count"]
            ms["avg_completeness"] = ms["avg_completeness"] / ms["count"]
            ms["completeness_rate"] = ms["complete_answers"] / ms["count"]
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "timestamp": datetime.now().isoformat(),
                "models_tested": list(model_stats.keys()),
            },
            "by_model": model_stats,
            "recommendations": self._generate_recommendations(model_stats),
        }
        
        return report
    
    def _generate_recommendations(self, model_stats: Dict) -> List[str]:
        """Generate optimization recommendations based on metrics"""
        recommendations = []
        
        for model, stats in model_stats.items():
            avg_tokens = stats["avg_tokens"]
            avg_cost = stats["avg_cost"]
            completeness = stats["completeness_rate"]
            
            if avg_tokens > 1500:
                recommendations.append(f"⚠️ {model}: HIGH TOKEN COUNT ({avg_tokens:.0f}). Consider further content filtering.")
            
            if avg_cost > 0.010:
                recommendations.append(f"💰 {model}: HIGH COST (${avg_cost:.6f}). Switch to smaller model or batch process.")
            
            if completeness < 0.9:
                recommendations.append(f"❌ {model}: INCOMPLETE ANSWERS ({completeness*100:.0f}%). Refine prompt format.")
            
            if avg_tokens < 500 and completeness > 0.95:
                recommendations.append(f"✅ {model}: OPTIMAL ({avg_tokens:.0f} tokens, {completeness*100:.0f}% complete). Keep this configuration.")
        
        if not recommendations:
            recommendations.append("✅ All models performing well. Monitor for any degradation.")
        
        return recommendations
    
    def compare_versions(self, before_metrics: List[Dict], after_metrics: List[Dict]) -> Dict:
        """Compare metrics before and after optimization"""
        
        def avg_metric(metrics: List[Dict], key: str) -> float:
            if not metrics:
                return 0
            return sum(m.get(key, 0) for m in metrics) / len(metrics)
        
        comparison = {
            "before": {
                "avg_tokens": avg_metric(before_metrics, "total_tokens"),
                "avg_cost_usd": avg_metric(before_metrics, "estimated_cost_usd"),
                "avg_latency_ms": avg_metric(before_metrics, "latency_ms"),
                "avg_completeness": avg_metric(before_metrics, "answer_completeness"),
            },
            "after": {
                "avg_tokens": avg_metric(after_metrics, "total_tokens"),
                "avg_cost_usd": avg_metric(after_metrics, "estimated_cost_usd"),
                "avg_latency_ms": avg_metric(after_metrics, "latency_ms"),
                "avg_completeness": avg_metric(after_metrics, "answer_completeness"),
            },
            "improvements": {}
        }
        
        # Calculate improvements
        if comparison["before"]["avg_tokens"] > 0:
            token_reduction = (1 - comparison["after"]["avg_tokens"] / comparison["before"]["avg_tokens"]) * 100
            comparison["improvements"]["token_reduction_percent"] = round(token_reduction, 1)
        
        if comparison["before"]["avg_cost_usd"] > 0:
            cost_reduction = (1 - comparison["after"]["avg_cost_usd"] / comparison["before"]["avg_cost_usd"]) * 100
            comparison["improvements"]["cost_reduction_percent"] = round(cost_reduction, 1)
        
        if comparison["before"]["avg_latency_ms"] > 0:
            latency_change = ((comparison["after"]["avg_latency_ms"] / comparison["before"]["avg_latency_ms"]) - 1) * 100
            comparison["improvements"]["latency_change_percent"] = round(latency_change, 1)
        
        completeness_change = comparison["after"]["avg_completeness"] - comparison["before"]["avg_completeness"]
        comparison["improvements"]["completeness_change"] = round(completeness_change, 3)
        
        return comparison
    
    def save_report(self, filename: str = "optimization_report.json"):
        """Save metrics to file"""
        report = self.get_optimization_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {filename}")
    
    def print_summary(self):
        """Print metrics summary to console"""
        if not self.metrics:
            print("No metrics collected yet")
            return
        
        report = self.get_optimization_report()
        
        print("\n" + "="*60)
        print("PERFORMANCE OPTIMIZATION REPORT")
        print("="*60)
        print(f"\nTotal Tests: {report['summary']['total_tests']}")
        print(f"Models Tested: {', '.join(report['summary']['models_tested'])}")
        
        print("\n📊 METRICS BY MODEL:")
        print("-"*60)
        
        for model, stats in report['by_model'].items():
            print(f"\n{model}:")
            print(f"  Avg Tokens: {stats['avg_tokens']:.0f}")
            print(f"  Avg Cost: ${stats['avg_cost']:.6f}")
            print(f"  Avg Latency: {stats['avg_latency_ms']:.0f}ms")
            print(f"  Completeness: {stats['avg_completeness']:.2%}")
            print(f"  Complete Answers: {stats['complete_answers']}/{stats['count']}")
        
        print("\n💡 RECOMMENDATIONS:")
        print("-"*60)
        for rec in report['recommendations']:
            print(f"  {rec}")
        print("\n" + "="*60 + "\n")
