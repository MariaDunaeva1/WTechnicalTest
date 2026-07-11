"""Conversation state for Option B.

Simple state machine:

    IN_PROGRESS --(answers all questions)--> COMPLETED

In-memory store (dict + async lock). This is an explicit, documented
limitation (see README): it doesn't survive a process restart and
doesn't scale to multiple replicas. That would require Redis or a
database, out of scope for this test (noted under "what I'd improve").
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
    """Async-safe in-memory session store.

    The lock prevents race conditions if, in theory, two concurrent
    answers arrived for the same session (shouldn't happen with a
    single client conversing, but it's cheap to guarantee).
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
            raise SessionNotFoundError(f"Session not found: {session_id}")
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