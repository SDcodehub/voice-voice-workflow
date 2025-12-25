"""
Load Test Runner - Orchestrates workers and manages the load test lifecycle.

Handles:
- Worker pool management with asyncio
- Ramp-up/ramp-down of virtual users
- Live statistics display
- Graceful shutdown
"""

import asyncio
import time
import logging
import signal
from typing import Optional, List
from datetime import datetime

try:
    from .config import LoadTestConfig, TestScenario
    from .audio_pool import AudioPool
    from .collector import ResultsCollector, RequestResult
    from .worker import VoiceWorker, WorkerConfig
except ImportError:
    from config import LoadTestConfig, TestScenario
    from audio_pool import AudioPool
    from collector import ResultsCollector, RequestResult
    from worker import VoiceWorker, WorkerConfig

logger = logging.getLogger(__name__)


class LoadTestRunner:
    """
    Orchestrates load test execution.
    
    Usage:
        config = LoadTestConfig.from_scenario(TestScenario.MEDIUM)
        runner = LoadTestRunner(config)
        
        # Run the test
        await runner.run()
        
        # Get results
        report = runner.collector.generate_report()
    """
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.audio_pool = AudioPool(
            audio_dir=config.audio_dir,
            required_sample_rate=config.sample_rate,
        )
        self.collector = ResultsCollector()
        
        self._workers: List[VoiceWorker] = []
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._stats_task: Optional[asyncio.Task] = None
    
    async def run(self) -> ResultsCollector:
        """
        Run the complete load test.
        
        Returns:
            ResultsCollector with all results.
        """
        logger.info("=" * 60)
        logger.info("STARTING LOAD TEST")
        logger.info("=" * 60)
        logger.info(f"Target:     {self.config.target_url}")
        logger.info(f"Max Users:  {self.config.max_users}")
        logger.info(f"Duration:   {self.config.total_duration:.0f}s")
        logger.info(f"Ramp Up:    {self.config.ramp_up_time:.0f}s")
        logger.info(f"Hold:       {self.config.hold_time:.0f}s")
        logger.info(f"Ramp Down:  {self.config.ramp_down_time:.0f}s")
        logger.info("=" * 60)
        
        # Load audio files
        try:
            num_files = self.audio_pool.load()
            logger.info(f"Loaded {num_files} audio files")
            logger.info(f"Audio pool: {self.audio_pool.summary()}")
        except Exception as e:
            logger.error(f"Failed to load audio files: {e}")
            raise
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_handler)
        
        self._running = True
        self.collector.start()
        
        try:
            # Start live stats display
            self._stats_task = asyncio.create_task(self._display_live_stats())
            
            # Execute the load profile
            await self._execute_load_profile()
            
        except asyncio.CancelledError:
            logger.info("Load test cancelled")
        
        finally:
            self._running = False
            self.collector.stop()
            
            # Cancel stats task
            if self._stats_task:
                self._stats_task.cancel()
                try:
                    await self._stats_task
                except asyncio.CancelledError:
                    pass
            
            # Stop all workers
            await self._stop_all_workers()
            
            # Print final summary
            self.collector.print_summary()
        
        return self.collector
    
    async def _execute_load_profile(self):
        """Execute the ramp-up, hold, ramp-down load profile."""
        start_time = time.time()
        
        # Phase 1: Ramp Up
        if self.config.ramp_up_time > 0:
            logger.info("Phase 1: Ramping up...")
            await self._ramp_up()
        else:
            # Instant start
            for _ in range(self.config.max_users):
                await self._add_worker()
        
        # Phase 2: Hold
        if self.config.hold_time > 0:
            logger.info(f"Phase 2: Holding at {len(self._workers)} users for {self.config.hold_time}s...")
            
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.hold_time,
                )
            except asyncio.TimeoutError:
                pass  # Normal end of hold period
        
        # Phase 3: Ramp Down
        if self.config.ramp_down_time > 0 and not self._shutdown_event.is_set():
            logger.info("Phase 3: Ramping down...")
            await self._ramp_down()
        
        logger.info("Load test completed")
    
    async def _ramp_up(self):
        """Gradually add workers over ramp_up_time."""
        if self.config.max_users <= 0:
            return
        
        interval = self.config.ramp_up_time / self.config.max_users
        
        for i in range(self.config.max_users):
            if self._shutdown_event.is_set():
                break
            
            await self._add_worker()
            
            if i < self.config.max_users - 1:
                await asyncio.sleep(interval)
        
        logger.info(f"Ramp up complete: {len(self._workers)} users active")
    
    async def _ramp_down(self):
        """Gradually remove workers over ramp_down_time."""
        if not self._workers:
            return
        
        num_workers = len(self._workers)
        interval = self.config.ramp_down_time / num_workers
        
        for i in range(num_workers):
            if self._shutdown_event.is_set():
                break
            
            if self._workers:
                await self._remove_worker()
            
            if i < num_workers - 1:
                await asyncio.sleep(interval)
        
        logger.info("Ramp down complete")
    
    async def _add_worker(self):
        """Add a new worker to the pool."""
        worker_id = len(self._workers)
        
        worker_config = WorkerConfig(
            worker_id=worker_id,
            target_url=self.config.target_url,
            language_code=self.config.language_code,
            sample_rate=self.config.sample_rate,
            chunk_size=self.config.chunk_size,
            chunk_delay=self.config.chunk_delay,
            request_timeout=self.config.request_timeout,
            think_time=self.config.think_time,
        )
        
        worker = VoiceWorker(
            config=worker_config,
            get_audio=self.audio_pool.get_next,
            on_result=self.collector.add_result,
        )
        
        self._workers.append(worker)
        
        # Start worker as async task
        task = asyncio.create_task(
            worker.start(max_requests=self.config.requests_per_user)
        )
        self._worker_tasks.append(task)
        
        logger.debug(f"Added worker {worker_id}, total: {len(self._workers)}")
    
    async def _remove_worker(self):
        """Remove a worker from the pool."""
        if not self._workers:
            return
        
        worker = self._workers.pop()
        worker.stop()
        
        # Also remove the corresponding task
        if self._worker_tasks:
            task = self._worker_tasks.pop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.debug(f"Removed worker, remaining: {len(self._workers)}")
    
    async def _stop_all_workers(self):
        """Stop all workers gracefully."""
        logger.info(f"Stopping {len(self._workers)} workers...")
        
        # Signal all workers to stop
        for worker in self._workers:
            worker.stop()
        
        # Cancel all tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        self._workers.clear()
        self._worker_tasks.clear()
        
        logger.info("All workers stopped")
    
    async def _display_live_stats(self):
        """Display live statistics periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.live_stats_interval)
                
                stats = self.collector.get_live_stats()
                
                print(
                    f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                    f"Users: {len(self._workers):3d} | "
                    f"Requests: {stats['total_requests']:5d} | "
                    f"Success: {stats['success_rate']*100:5.1f}% | "
                    f"RPS: {stats['requests_per_second']:5.2f} | "
                    f"E2E Avg: {stats['avg_e2e_latency']*1000:6.0f}ms",
                    end="",
                    flush=True,
                )
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error displaying stats: {e}")
        
        print()  # New line after stats
    
    def _signal_handler(self):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()


async def run_load_test(
    scenario: TestScenario = TestScenario.BASELINE,
    target_url: str = "localhost:50051",
    audio_dir: str = "./test_audio",
    output_file: Optional[str] = None,
    **kwargs,
) -> ResultsCollector:
    """
    Convenience function to run a load test.
    
    Args:
        scenario: Predefined test scenario.
        target_url: Voice gateway URL.
        audio_dir: Directory containing test audio files.
        output_file: Optional path to save JSON report.
        **kwargs: Additional config overrides.
    
    Returns:
        ResultsCollector with all results.
    """
    config = LoadTestConfig.from_scenario(
        scenario,
        target_url=target_url,
        audio_dir=audio_dir,
        output_file=output_file,
        **kwargs,
    )
    
    runner = LoadTestRunner(config)
    collector = await runner.run()
    
    # Save report if output file specified
    if output_file:
        collector.save_report(output_file, config.to_dict())
    
    return collector

