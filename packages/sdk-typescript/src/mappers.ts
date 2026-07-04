import type { paths } from "./generated/api-types.js";

type CaptureBody = paths["/v1/episodes"]["post"]["requestBody"]["content"]["application/json"];
type RememberBody = paths["/v1/memories"]["post"]["requestBody"]["content"]["application/json"];
type RetrieveBody =
  paths["/v1/memories/retrieve"]["post"]["requestBody"]["content"]["application/json"];
type RespondBody = paths["/v1/agent/respond"]["post"]["requestBody"]["content"]["application/json"];
type FeedbackBody =
  paths["/v1/retrievals/{retrieval_id}/feedback"]["post"]["requestBody"]["content"]["application/json"];
type ConsolidateBody =
  paths["/v1/sessions/{session_id}/consolidate"]["post"]["requestBody"]["content"]["application/json"];

import type {
  CaptureEventInput,
  CaptureInput,
  ConsolidateInput,
  FeedbackInput,
  RememberInput,
  RespondInput,
  RetrieveInput,
} from "./client-types.js";

export function toQuery(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  }
  return params.toString();
}

export function toCaptureBody(input: CaptureInput): CaptureBody {
  return stripUndefined({
    namespace_id: input.namespaceId,
    agent_id: input.agentId,
    session_id: input.sessionId,
    user_id: input.userId,
    project_id: input.projectId,
    events: input.events.map((event) =>
      stripUndefined({
        kind: event.kind,
        content: event.content,
        metadata: event.metadata,
      }),
    ),
  }) as CaptureBody;
}

export function toRememberBody(input: RememberInput): RememberBody {
  return stripUndefined({
    namespace_id: input.namespaceId,
    agent_id: input.agentId,
    subject: input.subject,
    key: input.key,
    content: input.content,
    type: input.type,
    user_id: input.userId,
    project_id: input.projectId,
    structured_value: input.structuredValue,
    confidence: input.confidence,
    importance: input.importance,
    criticality: input.criticality,
    applicability: input.applicability,
    source_episode_content: input.sourceEpisodeContent,
    source_episode_metadata: input.sourceEpisodeMetadata,
    graph_relations: input.graphRelations?.map((relation) =>
      stripUndefined({
        source: relation.source,
        relation: relation.relation,
        target: relation.target,
        source_type: relation.sourceType,
        target_type: relation.targetType,
      }),
    ),
    valid_until: input.validUntil,
  }) as RememberBody;
}

export function toRetrieveBody(input: RetrieveInput): RetrieveBody {
  return stripUndefined({
    namespace_id: input.namespaceId,
    agent_id: input.agentId,
    query: input.query,
    user_id: input.userId,
    project_id: input.projectId,
    task_type: input.taskType,
    token_budget: input.tokenBudget,
    limit: input.limit,
    graph_hops: input.graphHops,
  }) as RetrieveBody;
}

export function toRespondBody(input: RespondInput): RespondBody {
  return stripUndefined({
    namespace_id: input.namespaceId,
    agent_id: input.agentId,
    query: input.query,
    user_id: input.userId,
    project_id: input.projectId,
    task_type: input.taskType,
    token_budget: input.tokenBudget,
    limit: input.limit,
    graph_hops: input.graphHops,
    use_memory: input.useMemory,
  }) as RespondBody;
}

export function toFeedbackBody(input: FeedbackInput): FeedbackBody {
  return stripUndefined({
    outcome: input.outcome,
    source: input.source,
    memory_version_id: input.memoryVersionId,
    graph_edge_id: input.graphEdgeId,
    confidence: input.confidence,
    task_type: input.taskType,
  }) as FeedbackBody;
}

export function toConsolidateBody(input: ConsolidateInput): ConsolidateBody {
  return stripUndefined({
    namespace_id: input.namespaceId,
    agent_id: input.agentId,
    session_id: input.sessionId,
    user_id: input.userId,
    project_id: input.projectId,
  }) as ConsolidateBody;
}

export function stripUndefined<T extends Record<string, unknown>>(input: T): Partial<T> {
  return Object.fromEntries(Object.entries(input).filter((entry) => entry[1] !== undefined)) as
    Partial<T> | T;
}

export function readError(value: unknown): { code: string; message: string } {
  if (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof value.error === "object" &&
    value.error !== null &&
    "code" in value.error &&
    "message" in value.error
  ) {
    return {
      code: String(value.error.code),
      message: String(value.error.message),
    };
  }
  return { code: "http_error", message: "request failed" };
}
