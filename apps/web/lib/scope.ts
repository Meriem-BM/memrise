export const LOCAL_INSPECTOR_SCOPE = {
  namespaceId: "local",
  agentId: "coding-agent",
  sessionId: "session-1",
  userId: "user-1",
  projectId: "atlas",
} as const;

export function scopeQueryString(scope: {
  namespaceId: string;
  agentId: string;
  userId?: string;
  projectId?: string;
}): string {
  const params = new URLSearchParams();
  params.set("namespace_id", scope.namespaceId);
  params.set("agent_id", scope.agentId);
  if (scope.userId !== undefined) {
    params.set("user_id", scope.userId);
  }
  if (scope.projectId !== undefined) {
    params.set("project_id", scope.projectId);
  }
  return params.toString();
}
