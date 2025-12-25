#!/usr/bin/env python3
"""
Voice Gateway Load Test CLI

End-to-end load testing for the voice-to-voice AI pipeline.

Usage:
    # Basic test with defaults
    python load_test.py --audio-dir ./test_audio

    # Run a specific scenario
    python load_test.py --scenario medium --target localhost:50051

    # Custom configuration
    python load_test.py --users 20 --duration 300 --ramp-up 30

    # Save results
    python load_test.py --scenario heavy --output results.json

Examples:
    # Baseline (1 user, establish latency baseline)
    python load_test.py --scenario baseline

    # Light load (5 users, 2 minutes)
    python load_test.py --scenario light

    # Stress test (50 users, 5 minutes)
    python load_test.py --scenario heavy

    # Spike test (sudden burst to 100 users)
    python load_test.py --scenario spike
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from config import LoadTestConfig, TestScenario
from audio_pool import AudioPool, create_test_audio
from runner import LoadTestRunner


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on verbosity level."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
    )
    
    # Reduce noise from grpc
    logging.getLogger('grpc').setLevel(logging.WARNING)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Voice Gateway Load Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    # Target configuration
    parser.add_argument(
        "--target", "-t",
        default="localhost:50051",
        help="Voice gateway target URL (default: localhost:50051)",
    )
    
    # Audio configuration
    parser.add_argument(
        "--audio-dir", "-a",
        default="./test_audio",
        help="Directory containing test WAV files (default: ./test_audio)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Required audio sample rate in Hz (default: 16000)",
    )
    parser.add_argument(
        "--language",
        default="en-US",
        help="Language code for ASR (default: en-US)",
    )
    
    # Load configuration - scenario OR manual
    scenario_group = parser.add_mutually_exclusive_group()
    scenario_group.add_argument(
        "--scenario", "-s",
        type=str,
        choices=["baseline", "light", "medium", "heavy", "spike", "endurance"],
        help="Use a predefined test scenario",
    )
    scenario_group.add_argument(
        "--users", "-u",
        type=int,
        help="Maximum number of concurrent users (overrides scenario)",
    )
    
    # Manual timing configuration
    parser.add_argument(
        "--duration", "-d",
        type=float,
        help="Hold duration in seconds (default: depends on scenario)",
    )
    parser.add_argument(
        "--ramp-up",
        type=float,
        help="Ramp up time in seconds (default: depends on scenario)",
    )
    parser.add_argument(
        "--ramp-down",
        type=float,
        help="Ramp down time in seconds (default: depends on scenario)",
    )
    parser.add_argument(
        "--think-time",
        type=float,
        help="Think time between requests per user in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--requests-per-user",
        type=int,
        default=0,
        help="Max requests per user, 0=unlimited (default: 0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds (default: 60)",
    )
    
    # Output configuration
    parser.add_argument(
        "--output", "-o",
        help="Output file for JSON report",
    )
    parser.add_argument(
        "--output-raw",
        help="Output file for raw results (JSON)",
    )
    
    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    
    # Utilities
    parser.add_argument(
        "--create-test-audio",
        action="store_true",
        help="Create a test audio file (silence) in audio-dir",
    )
    parser.add_argument(
        "--list-audio",
        action="store_true",
        help="List available audio files and exit",
    )
    
    return parser.parse_args()


def create_config_from_args(args) -> LoadTestConfig:
    """Create LoadTestConfig from command line arguments."""
    
    # Start with scenario or defaults
    if args.scenario:
        scenario = TestScenario(args.scenario)
        config = LoadTestConfig.from_scenario(scenario)
    else:
        config = LoadTestConfig()
    
    # Override with explicit arguments
    config.target_url = args.target
    config.audio_dir = args.audio_dir
    config.sample_rate = args.sample_rate
    config.language_code = args.language
    config.request_timeout = args.timeout
    config.verbose = args.verbose
    config.debug = args.debug
    config.output_file = args.output
    
    if args.users is not None:
        config.max_users = args.users
    if args.duration is not None:
        config.hold_time = args.duration
    if args.ramp_up is not None:
        config.ramp_up_time = args.ramp_up
    if args.ramp_down is not None:
        config.ramp_down_time = args.ramp_down
    if args.think_time is not None:
        config.think_time = args.think_time
    if args.requests_per_user is not None:
        config.requests_per_user = args.requests_per_user
    
    return config


async def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose, args.debug)
    
    # Handle utility commands
    if args.create_test_audio:
        print(f"Creating test audio in {args.audio_dir}...")
        os.makedirs(args.audio_dir, exist_ok=True)
        filepath = create_test_audio(args.audio_dir, duration=3.0)
        print(f"Created: {filepath}")
        return 0
    
    if args.list_audio:
        try:
            pool = AudioPool(args.audio_dir, required_sample_rate=args.sample_rate)
            pool.load()
            summary = pool.summary()
            
            print(f"\nAudio files in {args.audio_dir}:")
            print("-" * 40)
            for f in summary.get("files", []):
                print(f"  {f}")
            print("-" * 40)
            print(f"Total: {summary['count']} files")
            print(f"Total duration: {summary['total_duration_seconds']:.2f}s")
            
        except Exception as e:
            print(f"Error: {e}")
            return 1
        
        return 0
    
    # Create configuration
    config = create_config_from_args(args)
    
    # Validate audio directory
    if not os.path.exists(config.audio_dir):
        print(f"Error: Audio directory not found: {config.audio_dir}")
        print(f"Create test audio with: python load_test.py --create-test-audio --audio-dir {config.audio_dir}")
        return 1
    
    # Run the load test
    try:
        runner = LoadTestRunner(config)
        collector = await runner.run()
        
        # Save outputs
        if config.output_file:
            collector.save_report(config.output_file, config.to_dict())
            print(f"\nReport saved to: {config.output_file}")
        
        if args.output_raw:
            collector.save_raw_results(args.output_raw)
            print(f"Raw results saved to: {args.output_raw}")
        
        # Return non-zero if there were errors
        report = collector.generate_report()
        success_rate = report.get("summary", {}).get("success_rate", 0)
        
        if success_rate < 0.95:
            print(f"\n⚠️  Warning: Success rate below 95% ({success_rate*100:.1f}%)")
            return 1
        
        return 0
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    
    except Exception as e:
        print(f"\nError: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

