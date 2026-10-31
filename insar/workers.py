"""Arka plan iş parçacıkları: arayüz donmadan ağ ve işleme çağrıları."""

from __future__ import annotations

import threading
import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    log = Signal(str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    """fn(log=..., should_stop=..., *args) çağırır; sonucu sinyalle döndürür."""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    @Slot()
    def run(self) -> None:
        try:
            res = self.fn(*self.args, log=self.signals.log.emit,
                          should_stop=self._stop.is_set, **self.kwargs)
            self.signals.result.emit(res)
        except InterruptedError as e:
            self.signals.error.emit(str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.signals.error.emit(f"{type(e).__name__}: {e}")
        finally:
            self.signals.finished.emit()
