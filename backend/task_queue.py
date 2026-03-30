"""
Sistema de cola de tareas serial para ejecucion con LLM local (Ollama).

Solo un task se ejecuta a la vez. Los demas esperan en cola FIFO.
Cada sesion tiene estado aislado (status, tokens, timer, cancel_event).
"""
import asyncio
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any


@dataclass
class SessionState:
    """Estado aislado por sesion de usuario."""
    session_id: str
    state: str = "idle"  # idle | queued | processing | success | error | cancelled | doc_ready
    message: str = ""
    log: List[str] = field(default_factory=list)
    start_time: float = 0.0
    tokens: Dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
    })
    cancel_event: threading.Event = field(default_factory=threading.Event)
    queue_position: int = 0  # 0 = ejecutando, 1+ = esperando
    task_type: str = ""  # "process-docs" | "generate" | "enhance-json"
    result_data: Optional[Any] = None  # Para almacenar resultados (ej: enhance-json)


class SessionManager:
    """Gestiona estados aislados por sesion (thread-safe)."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id=session_id)
            return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, state: str, message: str = ""):
        session = self.get(session_id)
        if not session:
            return
        if message and (not session.log or session.log[-1] != message):
            session.log.append(message)
        session.state = state
        session.message = message

    def add_tokens(self, session_id: str, usage: dict):
        session = self.get(session_id)
        if not session or not usage:
            return
        with self._lock:
            session.tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
            session.tokens["completion_tokens"] += usage.get("completion_tokens", 0)
            session.tokens["total_tokens"] += usage.get("total_tokens", 0)

    def get_status_dict(self, session_id: str) -> dict:
        """Retorna dict compatible con el formato que espera el frontend."""
        session = self.get(session_id)
        if not session:
            return {"state": "idle", "message": "", "queue_position": 0}
        elapsed = round(time.time() - session.start_time, 1) if session.start_time else 0
        return {
            "state": session.state,
            "message": session.message,
            "log": list(session.log),
            "timestamp": time.time(),
            "tokens": dict(session.tokens),
            "elapsed_seconds": elapsed,
            "queue_position": session.queue_position,
        }

    def cleanup(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)


class TaskQueue:
    """Cola FIFO con un solo worker. Ejecuta tareas de a una."""

    def __init__(self, session_manager: SessionManager):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._session_manager = session_manager
        self._current_task_session_id: Optional[str] = None
        self._ordered_ids: List[str] = []  # orden FIFO para calcular posiciones
        self._lock = threading.Lock()

    async def start_worker(self):
        asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        while True:
            session_id, func, args, kwargs = await self._queue.get()
            self._current_task_session_id = session_id

            # Sacar de la lista de espera y recalcular posiciones
            with self._lock:
                if session_id in self._ordered_ids:
                    self._ordered_ids.remove(session_id)
                self._update_queue_positions()

            session = self._session_manager.get(session_id)

            # Si fue cancelado mientras esperaba en cola, skip
            if session and session.cancel_event.is_set():
                session.state = "cancelled"
                session.message = "Cancelado antes de iniciar."
                self._queue.task_done()
                self._current_task_session_id = None
                continue

            # Marcar como processing
            if session:
                session.state = "processing"
                session.queue_position = 0
                session.start_time = time.time()

            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    _run_task_with_context,
                    session_id,
                    self._session_manager,
                    func,
                    args,
                    kwargs,
                )
            except Exception as e:
                if session:
                    session.state = "error"
                    session.message = f"Error: {e}"
                    if not session.log or session.log[-1] != session.message:
                        session.log.append(session.message)
            finally:
                self._queue.task_done()
                self._current_task_session_id = None

    async def enqueue(self, session_id: str, func: Callable, *args, **kwargs):
        session = self._session_manager.get_or_create(session_id)
        session.cancel_event.clear()
        session.log = []
        session.message = "En cola de espera..."
        session.state = "queued"

        with self._lock:
            self._ordered_ids.append(session_id)
            session.queue_position = len(self._ordered_ids)

        await self._queue.put((session_id, func, args, kwargs))
        self._update_queue_positions()

    def _update_queue_positions(self):
        for i, sid in enumerate(self._ordered_ids):
            session = self._session_manager.get(sid)
            if session:
                session.queue_position = i + 1
                session.message = f"En cola de espera... (posicion {i + 1})"

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def current_task_session(self) -> Optional[str]:
        return self._current_task_session_id


def _run_task_with_context(
    session_id: str,
    session_manager: SessionManager,
    func: Callable,
    args: tuple,
    kwargs: dict,
):
    """Wrapper que setea el contexto de sesion en el thread del executor antes de ejecutar."""
    from llm_client import set_current_session, clear_current_session
    set_current_session(session_id, session_manager)
    try:
        func(*args, **kwargs)
    finally:
        clear_current_session()
