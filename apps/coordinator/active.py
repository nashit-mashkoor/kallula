import asyncio


class ActiveRuns:
    def __init__(self) -> None:
        self._signals: dict[str, asyncio.Event] = {}

    def register(self, run_id: str) -> asyncio.Event:
        signal = asyncio.Event()
        self._signals[run_id] = signal
        return signal

    def unregister(self, run_id: str) -> None:
        self._signals.pop(run_id, None)

    def signal(self, run_id: str) -> bool:
        signal = self._signals.get(run_id)
        if signal is None:
            return False
        signal.set()
        return True

    def is_active(self, run_id: str) -> bool:
        return run_id in self._signals
