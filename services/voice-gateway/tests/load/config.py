"""
Load Test Configuration

Defines configuration dataclasses and pre-built test scenarios.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class TestScenario(Enum):
    """Pre-defined load test scenarios."""
    BASELINE = "baseline"       # Single user, establish baseline
    LIGHT = "light"             # 5 users, normal operation
    MEDIUM = "medium"           # 20 users, typical peak
    HEAVY = "heavy"             # 50 users, stress test
    SPIKE = "spike"             # Sudden burst to 100 users
    ENDURANCE = "endurance"     # 20 users for 30 minutes


@dataclass
class LoadTestConfig:
    """Configuration for load test execution."""
    
    # Connection settings
    target_url: str = "localhost:50051"
    use_ssl: bool = False
    
    # Audio settings
    audio_dir: str = "./test_audio"
    sample_rate: int = 16000
    language_code: str = "en-US"
    
    # Load settings
    max_users: int = 10
    ramp_up_time: float = 10.0      # Seconds to reach max users
    hold_time: float = 60.0         # Seconds to hold at max users
    ramp_down_time: float = 5.0     # Seconds to scale down
    
    # Request settings
    requests_per_user: int = 0      # 0 = unlimited (run until duration ends)
    think_time: float = 1.0         # Seconds between requests per user
    request_timeout: float = 60.0   # Timeout per request in seconds
    
    # Audio streaming settings
    chunk_size: int = 4096          # Bytes per audio chunk
    chunk_delay: float = 0.01       # Delay between chunks (simulates real-time)
    
    # Output settings
    output_file: Optional[str] = None       # JSON results file
    csv_file: Optional[str] = None          # CSV results file
    live_stats_interval: float = 5.0        # Seconds between live stats updates
    
    # Verbosity
    verbose: bool = False
    debug: bool = False
    
    @classmethod
    def from_scenario(cls, scenario: TestScenario, **overrides) -> "LoadTestConfig":
        """Create config from a predefined scenario."""
        
        scenarios = {
            TestScenario.BASELINE: {
                "max_users": 1,
                "ramp_up_time": 0,
                "hold_time": 30,
                "ramp_down_time": 0,
                "requests_per_user": 10,
                "think_time": 2.0,
            },
            TestScenario.LIGHT: {
                "max_users": 5,
                "ramp_up_time": 10,
                "hold_time": 120,
                "ramp_down_time": 5,
                "think_time": 2.0,
            },
            TestScenario.MEDIUM: {
                "max_users": 20,
                "ramp_up_time": 30,
                "hold_time": 300,
                "ramp_down_time": 10,
                "think_time": 1.5,
            },
            TestScenario.HEAVY: {
                "max_users": 50,
                "ramp_up_time": 60,
                "hold_time": 300,
                "ramp_down_time": 15,
                "think_time": 1.0,
            },
            TestScenario.SPIKE: {
                "max_users": 100,
                "ramp_up_time": 5,      # Fast ramp
                "hold_time": 30,
                "ramp_down_time": 5,
                "think_time": 0.5,
            },
            TestScenario.ENDURANCE: {
                "max_users": 20,
                "ramp_up_time": 30,
                "hold_time": 1800,       # 30 minutes
                "ramp_down_time": 10,
                "think_time": 3.0,
            },
        }
        
        config_dict = scenarios.get(scenario, {})
        config_dict.update(overrides)
        return cls(**config_dict)
    
    @property
    def total_duration(self) -> float:
        """Total test duration in seconds."""
        return self.ramp_up_time + self.hold_time + self.ramp_down_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "target_url": self.target_url,
            "use_ssl": self.use_ssl,
            "audio_dir": self.audio_dir,
            "sample_rate": self.sample_rate,
            "language_code": self.language_code,
            "max_users": self.max_users,
            "ramp_up_time": self.ramp_up_time,
            "hold_time": self.hold_time,
            "ramp_down_time": self.ramp_down_time,
            "requests_per_user": self.requests_per_user,
            "think_time": self.think_time,
            "request_timeout": self.request_timeout,
            "total_duration": self.total_duration,
        }

