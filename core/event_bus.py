import asyncio
import logging
from typing import Callable, Dict, List, Any, Awaitable

class EventBus:
    """
    Phase 2: Asynchronous & Event-Driven Architecture.
    A decoupled Pub/Sub messaging system allowing different S.A.I. modules
    to communicate asynchronously without tight coupling.
    """

    def __init__(self):
        self.logger = logging.getLogger("SAI.EventBus")
        # Maps event names to a list of async callback functions
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        # The main async queue holding (event_name, payload) tuples
        self._queue = asyncio.Queue()
        self._running = False
        self._worker_task = None

    def _ensure_worker(self):
        if self._running and self._worker_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._worker_task = loop.create_task(self._worker())
                self.logger.info("EventBus worker initialized.")
            except RuntimeError:
                pass # Still no running event loop

    def subscribe(self, event_name: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Registers an asynchronous callback for a specific event."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
        self.logger.debug(f"Subscribed {callback.__name__} to event '{event_name}'")

    def publish(self, event_name: str, payload: Dict[str, Any] = None):
        """Non-blocking publish. Puts the event into the queue."""
        self._ensure_worker()
        if payload is None:
            payload = {}
        self._queue.put_nowait((event_name, payload))

    async def _worker(self):
        """Continuously pulls events from the queue and distributes them to subscribers."""
        self.logger.info("EventBus worker started.")
        while self._running:
            try:
                event_name, payload = await self._queue.get()
                
                if event_name in self._subscribers:
                    # Execute all callbacks for this event concurrently
                    callbacks = self._subscribers[event_name]
                    tasks = [asyncio.create_task(cb(payload)) for cb in callbacks]
                    if tasks:
                        # We don't await tasks directly here because we want fire-and-forget,
                        # but we can gather them to capture unhandled exceptions if we wanted.
                        # For pure decoupled async, we let the event loop handle them.
                        pass
                
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing event {event_name}: {e}")

    def start(self):
        """Starts the event bus background worker."""
        if not self._running:
            self._running = True
            self._ensure_worker()
            self.logger.info("EventBus fully operational.")

    async def stop(self):
        """Stops the event bus gracefully."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.logger.info("EventBus shutdown.")
