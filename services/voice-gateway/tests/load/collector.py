"""
Results Collector - Aggregates metrics from load test workers.

Provides real-time statistics, percentile calculations, and report generation.
"""

import time
import json
import statistics
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from collections import defaultdict
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


@dataclass
class RequestResult:
    """Result of a single voice request."""
    
    # Identification
    worker_id: int
    request_id: int
    audio_file: str
    
    # Timing (all in seconds)
    start_time: float
    end_time: float
    
    # Component latencies (seconds, None if not captured)
    asr_latency: Optional[float] = None
    llm_ttft: Optional[float] = None
    llm_total: Optional[float] = None
    tts_latency: Optional[float] = None
    e2e_latency: Optional[float] = None
    
    # Results
    status: str = "success"  # success, error, timeout
    error_message: Optional[str] = None
    transcript: Optional[str] = None
    response_text: Optional[str] = None
    
    @property
    def total_duration(self) -> float:
        """Total request duration in seconds."""
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class AggregateStats:
    """Aggregated statistics for a metric."""
    count: int = 0
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    median: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    stddev: float = 0.0
    
    @classmethod
    def from_values(cls, values: List[float]) -> "AggregateStats":
        """Calculate statistics from a list of values."""
        if not values:
            return cls()
        
        sorted_values = sorted(values)
        n = len(values)
        
        return cls(
            count=n,
            min=sorted_values[0],
            max=sorted_values[-1],
            mean=statistics.mean(values),
            median=statistics.median(values),
            p90=sorted_values[int(n * 0.90)] if n > 1 else sorted_values[0],
            p95=sorted_values[int(n * 0.95)] if n > 1 else sorted_values[0],
            p99=sorted_values[int(n * 0.99)] if n > 1 else sorted_values[0],
            stddev=statistics.stdev(values) if n > 1 else 0.0,
        )


class ResultsCollector:
    """
    Thread-safe collector for load test results.
    
    Usage:
        collector = ResultsCollector()
        
        # Workers submit results
        collector.add_result(result)
        
        # Get live stats
        stats = collector.get_live_stats()
        
        # Generate final report
        report = collector.generate_report()
    """
    
    def __init__(self):
        self._results: List[RequestResult] = []
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        
        # Live counters (for real-time stats without locking full list)
        self._success_count = 0
        self._error_count = 0
        self._timeout_count = 0
    
    def start(self):
        """Mark the start of the load test."""
        self._start_time = time.time()
    
    def stop(self):
        """Mark the end of the load test."""
        self._end_time = time.time()
    
    def add_result(self, result: RequestResult):
        """Add a request result (thread-safe)."""
        with self._lock:
            self._results.append(result)
            
            if result.status == "success":
                self._success_count += 1
            elif result.status == "error":
                self._error_count += 1
            elif result.status == "timeout":
                self._timeout_count += 1
    
    def get_live_stats(self) -> Dict[str, Any]:
        """
        Get current statistics for live display.
        Returns lightweight stats without full aggregation.
        """
        with self._lock:
            total = len(self._results)
            if total == 0:
                return {
                    "total_requests": 0,
                    "success_rate": 0.0,
                    "avg_latency": 0.0,
                }
            
            # Get last N results for recent latency
            recent = self._results[-min(100, total):]
            recent_latencies = [
                r.e2e_latency for r in recent 
                if r.e2e_latency is not None and r.status == "success"
            ]
            
            elapsed = time.time() - (self._start_time or time.time())
            
            return {
                "total_requests": total,
                "success_count": self._success_count,
                "error_count": self._error_count,
                "timeout_count": self._timeout_count,
                "success_rate": self._success_count / total if total > 0 else 0.0,
                "elapsed_seconds": elapsed,
                "requests_per_second": total / elapsed if elapsed > 0 else 0.0,
                "avg_e2e_latency": (
                    statistics.mean(recent_latencies) 
                    if recent_latencies else 0.0
                ),
            }
    
    def generate_report(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate comprehensive load test report.
        
        Args:
            config: Optional test configuration to include in report.
        
        Returns:
            Complete report as dictionary.
        """
        with self._lock:
            results = self._results.copy()
        
        if not results:
            return {
                "status": "no_data",
                "message": "No results collected",
            }
        
        # Separate by status
        success_results = [r for r in results if r.status == "success"]
        error_results = [r for r in results if r.status == "error"]
        timeout_results = [r for r in results if r.status == "timeout"]
        
        # Calculate duration
        total_duration = (self._end_time or time.time()) - (self._start_time or 0)
        
        report = {
            "summary": {
                "timestamp": datetime.now().isoformat(),
                "total_duration_seconds": total_duration,
                "total_requests": len(results),
                "successful_requests": len(success_results),
                "failed_requests": len(error_results),
                "timeout_requests": len(timeout_results),
                "success_rate": len(success_results) / len(results) if results else 0,
                "requests_per_second": len(results) / total_duration if total_duration > 0 else 0,
            },
            "latency": {},
            "errors": [],
        }
        
        # Latency statistics (only from successful requests)
        if success_results:
            # E2E Latency
            e2e_values = [r.e2e_latency for r in success_results if r.e2e_latency]
            if e2e_values:
                report["latency"]["e2e"] = asdict(AggregateStats.from_values(e2e_values))
            
            # ASR Latency
            asr_values = [r.asr_latency for r in success_results if r.asr_latency]
            if asr_values:
                report["latency"]["asr"] = asdict(AggregateStats.from_values(asr_values))
            
            # LLM TTFT
            llm_ttft_values = [r.llm_ttft for r in success_results if r.llm_ttft]
            if llm_ttft_values:
                report["latency"]["llm_ttft"] = asdict(AggregateStats.from_values(llm_ttft_values))
            
            # LLM Total
            llm_total_values = [r.llm_total for r in success_results if r.llm_total]
            if llm_total_values:
                report["latency"]["llm_total"] = asdict(AggregateStats.from_values(llm_total_values))
            
            # TTS Latency
            tts_values = [r.tts_latency for r in success_results if r.tts_latency]
            if tts_values:
                report["latency"]["tts"] = asdict(AggregateStats.from_values(tts_values))
            
            # Total Duration
            duration_values = [r.total_duration for r in success_results]
            report["latency"]["total_duration"] = asdict(AggregateStats.from_values(duration_values))
        
        # Error summary
        if error_results:
            error_messages = defaultdict(int)
            for r in error_results:
                msg = r.error_message or "Unknown error"
                error_messages[msg] += 1
            
            report["errors"] = [
                {"message": msg, "count": count}
                for msg, count in sorted(error_messages.items(), key=lambda x: -x[1])
            ]
        
        # Include config if provided
        if config:
            report["config"] = config
        
        return report
    
    def save_report(self, filepath: str, config: Optional[Dict] = None):
        """Save report to JSON file."""
        report = self.generate_report(config)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to {filepath}")
    
    def save_raw_results(self, filepath: str):
        """Save raw results to JSON for detailed analysis."""
        with self._lock:
            data = [r.to_dict() for r in self._results]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Raw results saved to {filepath}")
    
    def print_summary(self):
        """Print a human-readable summary to console."""
        report = self.generate_report()
        
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        
        summary = report.get("summary", {})
        print(f"\nDuration:        {summary.get('total_duration_seconds', 0):.2f}s")
        print(f"Total Requests:  {summary.get('total_requests', 0)}")
        print(f"Successful:      {summary.get('successful_requests', 0)}")
        print(f"Failed:          {summary.get('failed_requests', 0)}")
        print(f"Success Rate:    {summary.get('success_rate', 0) * 100:.1f}%")
        print(f"Throughput:      {summary.get('requests_per_second', 0):.2f} req/s")
        
        latency = report.get("latency", {})
        if "e2e" in latency:
            e2e = latency["e2e"]
            print(f"\nEnd-to-End Latency:")
            print(f"  P50:  {e2e.get('median', 0) * 1000:.0f}ms")
            print(f"  P95:  {e2e.get('p95', 0) * 1000:.0f}ms")
            print(f"  P99:  {e2e.get('p99', 0) * 1000:.0f}ms")
            print(f"  Max:  {e2e.get('max', 0) * 1000:.0f}ms")
        
        if report.get("errors"):
            print(f"\nTop Errors:")
            for err in report["errors"][:5]:
                print(f"  [{err['count']}x] {err['message'][:50]}")
        
        print("\n" + "=" * 60)

