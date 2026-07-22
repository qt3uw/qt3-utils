from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import numpy as np
import nidaqmx
from nidaqmx.constants import AcquisitionType

logger = logging.getLogger(__name__)


class NidaqTimedAnalogMean:
    """
    Finite analog voltage acquisition on one AI channel, timed like NidaqTimedRateCounter.

    Uses the same method names as the counter stack so ScanController / ScopeController
    need no logic forks: ``sample_batch_counts`` returns the **mean voltage (V)** over
    each integration window (not a count).
    """

    def __init__(
        self,
        daq_name: str = 'Dev1',
        channel: str = 'ai1',
        clock_rate: int = 100000,
        sample_time_in_seconds: float = 1.0,
        read_write_timeout: float = 10.0,
        min_val: float = -10.0,
        max_val: float = 10.0,
    ) -> None:
        self.daq_name = daq_name
        self.channel = channel
        self.clock_rate = clock_rate
        self.sample_time_in_seconds = sample_time_in_seconds
        self.read_write_timeout = read_write_timeout
        self.min_val = min_val
        self.max_val = max_val

        self.num_data_samples_per_batch = max(
            2, int(sample_time_in_seconds * clock_rate)
        )
        self.running = False
        self.read_lock = False
        self.ai_task: Optional[nidaqmx.Task] = None

    def configure(self, config_dict: dict) -> None:
        self.daq_name = config_dict.get('daq_name', self.daq_name)
        self.channel = config_dict.get('channel', self.channel)
        self.clock_rate = config_dict.get('clock_rate', self.clock_rate)
        self.sample_time_in_seconds = config_dict.get(
            'sample_time_in_seconds', self.sample_time_in_seconds
        )
        self.read_write_timeout = config_dict.get(
            'read_write_timeout', self.read_write_timeout
        )
        self.min_val = config_dict.get('min_val', self.min_val)
        self.max_val = config_dict.get('max_val', self.max_val)
        self.num_data_samples_per_batch = max(
            2, int(self.sample_time_in_seconds * self.clock_rate)
        )

    def _physical_channel(self) -> str:
        ch = self.channel.strip()
        if '/' in ch:
            return ch
        return f'{self.daq_name}/{ch}'

    def _build_task(self) -> nidaqmx.Task:
        task = nidaqmx.Task()
        task.ai_channels.add_ai_voltage_chan(
            self._physical_channel(),
            min_val=self.min_val,
            max_val=self.max_val,
        )
        task.timing.cfg_samp_clk_timing(
            self.clock_rate,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=self.num_data_samples_per_batch,
        )
        return task

    def _rebuild_task_if_running(self) -> None:
        if not self.running:
            return
        if self.ai_task is not None:
            try:
                self.ai_task.stop()
            except Exception as e:
                logger.debug('ai_task.stop in rebuild: %s', e)
            try:
                self.ai_task.close()
            except Exception as e:
                logger.debug('ai_task.close in rebuild: %s', e)
            self.ai_task = None
        self.ai_task = self._build_task()

    def _configure_daq(self) -> None:
        if self.ai_task is not None:
            try:
                self.ai_task.stop()
            except Exception:
                pass
            try:
                self.ai_task.close()
            except Exception:
                pass
            self.ai_task = None
        self.ai_task = self._build_task()

    def start(self) -> None:
        if self.running:
            self.stop()
        self._configure_daq()
        self.running = True

    def stop(self) -> None:
        if self.running:
            while self.read_lock:
                time.sleep(0.1)
            if self.ai_task is not None:
                try:
                    self.ai_task.stop()
                except Exception as e:
                    logger.debug(e)
                try:
                    self.ai_task.close()
                except Exception as e:
                    logger.debug(e)
                self.ai_task = None
        self.running = False

    def configure_sample_time(self, sample_time: float) -> None:
        self.sample_time_in_seconds = sample_time
        self.num_data_samples_per_batch = max(
            2, int(sample_time * self.clock_rate)
        )
        self._rebuild_task_if_running()

    def _read_samples(self) -> Tuple[np.ndarray, int]:
        if not self.running or self.ai_task is None:
            return np.zeros(1), 0
        try:
            self.read_lock = True
            self.ai_task.start()
            self.ai_task.wait_until_done(timeout=self.read_write_timeout)
            data = self.ai_task.read(
                number_of_samples_per_channel=self.num_data_samples_per_batch,
                timeout=self.read_write_timeout,
            )
            arr = np.asarray(data, dtype=np.float64).ravel()
            samples_read = int(arr.size)
            return arr, samples_read
        except Exception as e:
            logger.error('%s: %s', type(e), e)
            raise
        finally:
            try:
                self.ai_task.stop()
            except Exception as e:
                logger.debug('finally ai stop: %s', e)
            self.read_lock = False

    def sample_batch_counts(self) -> float:
        if not self.running:
            return 0.0
        data_sample, samples_read = self._read_samples()
        if samples_read <= 0:
            return 0.0
        return float(np.mean(data_sample[:samples_read]))

    def sample_nbatches_counts(
        self, n_batches: int = 1, sum_counts: bool = True
    ) -> np.ndarray:
        means: list[float] = []
        sample_counts: list[int] = []
        for _ in range(n_batches):
            data_sample, samples_read = self._read_samples()
            if samples_read > 0:
                means.append(float(np.mean(data_sample[:samples_read])))
            else:
                means.append(0.0)
            sample_counts.append(samples_read)

        m = np.asarray(means, dtype=np.float64)
        sc = np.asarray(sample_counts, dtype=np.float64)
        if sum_counts:
            total_s = float(np.sum(sc))
            if total_s > 0:
                wmean = float(np.sum(m * sc) / total_s)
            else:
                wmean = 0.0
            return np.array([wmean], dtype=np.float64)
        return m
