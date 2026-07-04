from dataclasses import dataclass

from memrise.consolidation.session_consolidation import SessionConsolidationService
from memrise.graph.projection import GraphProjectionService, GraphRebuildService
from memrise.learning.lifecycle import LifecycleService
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.graph_store import GraphClaimStore
from memrise.ports.providers import CompletionProvider, EmbeddingProvider, TokenCounter
from memrise.ports.repositories import JobQueue, MemoryStore
from memrise.ports.schema_registry import GraphSchemaRegistry
from memrise.read.explanation import ExplanationService
from memrise.read.retrieval import RetrievalService
from memrise.runtime.clock import SystemClock
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.job_processor import JobProcessor
from memrise.write.importance import ImportanceGate
from memrise.write.service import WriteService


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    write: WriteService
    retrieval: RetrievalService
    explain: ExplanationService
    job_processor: JobProcessor
    clock: SystemClock
    ids: UuidGenerator
    lifecycle: LifecycleService


def build_runtime_services(
    *,
    store: MemoryStore,
    jobs: JobQueue,
    graph_repository: GraphRepository,
    graph_projection: GraphProjectionService,
    graph_claim_store: GraphClaimStore | None,
    graph_rebuild: GraphRebuildService | None,
    schema_registry: GraphSchemaRegistry | None,
    completion_provider: CompletionProvider,
    embedding_provider: EmbeddingProvider,
    token_counter: TokenCounter,
    usefulness_half_life_days: float = 30.0,
) -> RuntimeServices:
    ids = UuidGenerator()
    write = WriteService(
        store=store,
        jobs=jobs,
        completion_provider=completion_provider,
        embedding_provider=embedding_provider,
        importance_gate=ImportanceGate(),
        id_generator=ids,
        schema_registry=schema_registry,
    )
    retrieval = RetrievalService(
        store=store,
        graph_repository=graph_repository,
        graph_claim_store=graph_claim_store,
        embedding_provider=embedding_provider,
        token_counter=token_counter,
        ids=ids,
    )
    explain = ExplanationService(store, graph_repository=graph_repository)
    lifecycle = LifecycleService(
        store=store,
        claim_store=graph_claim_store,
        graph_repository=graph_repository,
        half_life_days=usefulness_half_life_days,
    )
    job_processor = JobProcessor(
        store=store,
        write=write,
        graph_projection=graph_projection,
        graph_rebuild=graph_rebuild,
        session_consolidation=SessionConsolidationService(
            store=store,
            write=write,
            completion_provider=completion_provider,
            embedding_provider=embedding_provider,
        ),
        lifecycle=lifecycle,
    )
    return RuntimeServices(
        write=write,
        retrieval=retrieval,
        explain=explain,
        job_processor=job_processor,
        clock=SystemClock(),
        ids=ids,
        lifecycle=lifecycle,
    )
