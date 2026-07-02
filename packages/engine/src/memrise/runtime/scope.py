from memrise.core.models import Scope


def scope_from_namespace_agent(
    *,
    namespace_id: str,
    agent_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
) -> Scope:
    return Scope(
        namespace_id=namespace_id,
        agent_id=agent_id,
        user_id=user_id,
        project_id=project_id,
    )
