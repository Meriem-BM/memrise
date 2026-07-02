from enum import StrEnum


class EpisodeKind(StrEnum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    USER_FEEDBACK = "user_feedback"
    TASK_RESULT = "task_result"
    ENVIRONMENT_OBSERVATION = "environment_observation"


class MemoryType(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    GOAL = "goal"
    LESSON = "lesson"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CONTESTED = "contested"
    DELETED = "deleted"


class Criticality(StrEnum):
    NORMAL = "normal"
    HIGH_PRIORITY = "high_priority"
    MUST_INCLUDE = "must_include"


class MemoryOperation(StrEnum):
    ADD = "ADD"
    REINFORCE = "REINFORCE"
    SUPERSEDE = "SUPERSEDE"
    CONTEST = "CONTEST"
    NOOP = "NOOP"


class GraphEdgeStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CONTESTED = "contested"
    DELETED = "deleted"


class RetrievalSourceType(StrEnum):
    CRITICAL = "critical"
    STRUCTURED = "structured"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"


class FeedbackOutcome(StrEnum):
    HELPFUL = "helpful"
    UNUSED = "unused"
    HARMFUL = "harmful"


class FeedbackSource(StrEnum):
    USER = "user"
    DEVELOPER = "developer"
    TOOL = "tool"
    EVALUATOR = "evaluator"
    AGENT = "agent"


class JobType(StrEnum):
    EXTRACT_EPISODE = "extract_episode"
    CONSOLIDATE_SESSION = "consolidate_session"
    EXPIRE_MEMORIES = "expire_memories"
    PROCESS_FEEDBACK = "process_feedback"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE = "retryable"
