"""Estado conversacional para Option B.

Máquina de estados simple:

    IN_PROGRESS --(responde todas las preguntas)--> COMPLETED

Almacén en memoria (dict + lock async). Es una limitación explícita y
documentada en el README: no sobrevive a un reinicio del proceso ni
escala a varias réplicas. Para eso haría falta Redis o una base de datos,
fuera del alcance de esta prueba (lo indico como "qué mejoraría").
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.domain.questions import Question, total_questions
from app.domain.schemas import Answer


class ConversationStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class ConversationSession:
    session_id: str
    answers: list[Answer] = field(default_factory=list)
    status: ConversationStatus = ConversationStatus.IN_PROGRESS

    @property
    def next_question_index(self) -> int:
        return len(self.answers)

    def is_complete(self) -> bool:
        return len(self.answers) >= total_questions()


class SessionNotFoundError(Exception):
    pass


class SessionAlreadyCompletedError(Exception):
    pass


class SessionStore:
    """Almacén async-safe de sesiones en memoria.

    El lock evita condiciones de carrera si, en teoría, llegasen dos
    respuestas concurrentes para la misma sesión (no debería pasar con un
    solo cliente conversando, pero es barato de garantizar).
    """

    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> ConversationSession:
        session = ConversationSession(session_id=str(uuid.uuid4()))
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str) -> ConversationSession:
        async with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Sesión no encontrada: {session_id}")
        return session

    async def add_answer(self, session_id: str, answer: Answer) -> ConversationSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(f"Session not found: {session_id}")
            if session.status == ConversationStatus.COMPLETED:
                raise SessionAlreadyCompletedError(f"Session already completed: {session_id}")
            session.answers.append(answer)
            if session.is_complete():
                session.status = ConversationStatus.COMPLETED
        return session
