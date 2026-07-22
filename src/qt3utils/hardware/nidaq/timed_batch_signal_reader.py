"""Protocol for DAQ readers used by qt3scan/qt3scope (counter or analog mean)."""

from __future__ import annotations

from typing import Protocol, Union, runtime_checkable

import numpy as np


@runtime_checkable
class TimedBatchSignalReader(Protocol):
    """Timed batch acquisition with the same call pattern as NidaqTimedRateCounter."""

    def configure(self, config_dict: dict) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def configure_sample_time(self, sample_time: float) -> None: ...

    def sample_batch_counts(self) -> Union[int, float]: ...

    def sample_nbatches_counts(
        self, n_batches: int = 1, sum_counts: bool = True
    ) -> np.ndarray: ...
