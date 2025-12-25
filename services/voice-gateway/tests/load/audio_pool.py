"""
Audio Pool - Manages test audio files for load testing.

Loads WAV files from a directory and provides them to workers.
Supports round-robin, random, and weighted selection strategies.
"""

import os
import wave
import random
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Iterator
from enum import Enum

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """How to select audio files for workers."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    SEQUENTIAL = "sequential"


@dataclass
class AudioFile:
    """Represents a loaded audio file."""
    path: str
    name: str
    data: bytes
    sample_rate: int
    channels: int
    sample_width: int
    duration_seconds: float
    num_frames: int
    
    def get_chunks(self, chunk_size: int = 4096) -> Iterator[bytes]:
        """Yield audio data in chunks."""
        for i in range(0, len(self.data), chunk_size):
            yield self.data[i:i + chunk_size]


class AudioPool:
    """
    Manages a pool of test audio files for load testing.
    
    Usage:
        pool = AudioPool("./test_audio")
        pool.load()
        
        # Get audio for each worker
        audio = pool.get_next()
        for chunk in audio.get_chunks(4096):
            # send chunk
    """
    
    def __init__(
        self,
        audio_dir: str,
        strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN,
        required_sample_rate: int = 16000,
    ):
        self.audio_dir = Path(audio_dir)
        self.strategy = strategy
        self.required_sample_rate = required_sample_rate
        
        self._files: List[AudioFile] = []
        self._index = 0
        self._loaded = False
    
    def load(self) -> int:
        """
        Load all WAV files from the audio directory.
        
        Returns:
            Number of files loaded.
        
        Raises:
            FileNotFoundError: If audio directory doesn't exist.
            ValueError: If no valid WAV files found.
        """
        if not self.audio_dir.exists():
            raise FileNotFoundError(f"Audio directory not found: {self.audio_dir}")
        
        wav_files = list(self.audio_dir.glob("*.wav"))
        
        if not wav_files:
            raise ValueError(f"No WAV files found in {self.audio_dir}")
        
        self._files = []
        
        for wav_path in wav_files:
            try:
                audio_file = self._load_wav(wav_path)
                
                # Validate sample rate
                if audio_file.sample_rate != self.required_sample_rate:
                    logger.warning(
                        f"Skipping {wav_path.name}: sample rate {audio_file.sample_rate} "
                        f"!= required {self.required_sample_rate}"
                    )
                    continue
                
                self._files.append(audio_file)
                logger.info(
                    f"Loaded: {audio_file.name} "
                    f"({audio_file.duration_seconds:.2f}s, {audio_file.sample_rate}Hz)"
                )
                
            except Exception as e:
                logger.warning(f"Failed to load {wav_path}: {e}")
        
        if not self._files:
            raise ValueError(
                f"No valid WAV files found with sample rate {self.required_sample_rate}Hz"
            )
        
        self._loaded = True
        logger.info(f"Loaded {len(self._files)} audio files from {self.audio_dir}")
        
        return len(self._files)
    
    def _load_wav(self, path: Path) -> AudioFile:
        """Load a single WAV file."""
        with wave.open(str(path), 'rb') as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            num_frames = wf.getnframes()
            data = wf.readframes(num_frames)
            
            duration = num_frames / sample_rate
            
            return AudioFile(
                path=str(path),
                name=path.name,
                data=data,
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
                duration_seconds=duration,
                num_frames=num_frames,
            )
    
    def get_next(self) -> AudioFile:
        """
        Get the next audio file based on selection strategy.
        
        Raises:
            RuntimeError: If pool not loaded.
        """
        if not self._loaded:
            raise RuntimeError("AudioPool not loaded. Call load() first.")
        
        if self.strategy == SelectionStrategy.ROUND_ROBIN:
            audio = self._files[self._index % len(self._files)]
            self._index += 1
            return audio
        
        elif self.strategy == SelectionStrategy.RANDOM:
            return random.choice(self._files)
        
        elif self.strategy == SelectionStrategy.SEQUENTIAL:
            if self._index >= len(self._files):
                raise StopIteration("All audio files have been used")
            audio = self._files[self._index]
            self._index += 1
            return audio
        
        raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def get_all(self) -> List[AudioFile]:
        """Get all loaded audio files."""
        return self._files.copy()
    
    def reset(self):
        """Reset the selection index."""
        self._index = 0
    
    @property
    def count(self) -> int:
        """Number of loaded audio files."""
        return len(self._files)
    
    @property
    def total_duration(self) -> float:
        """Total duration of all audio files in seconds."""
        return sum(f.duration_seconds for f in self._files)
    
    def summary(self) -> dict:
        """Get summary statistics about the audio pool."""
        if not self._files:
            return {"loaded": False, "count": 0}
        
        durations = [f.duration_seconds for f in self._files]
        
        return {
            "loaded": True,
            "count": len(self._files),
            "total_duration_seconds": sum(durations),
            "min_duration_seconds": min(durations),
            "max_duration_seconds": max(durations),
            "avg_duration_seconds": sum(durations) / len(durations),
            "files": [f.name for f in self._files],
        }


def create_test_audio(output_dir: str, duration: float = 2.0, sample_rate: int = 16000):
    """
    Create a test audio file with silence (for testing without real audio).
    
    Args:
        output_dir: Directory to save the file.
        duration: Duration in seconds.
        sample_rate: Sample rate in Hz.
    """
    import struct
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    filepath = output_path / f"silence_{duration}s.wav"
    
    num_samples = int(duration * sample_rate)
    
    # Generate silence (zeros)
    audio_data = struct.pack(f'{num_samples}h', *([0] * num_samples))
    
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data)
    
    logger.info(f"Created test audio: {filepath}")
    return str(filepath)

