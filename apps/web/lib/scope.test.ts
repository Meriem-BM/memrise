import { describe, expect, it } from "vitest";

import { scopeQueryString } from "./scope";

describe("scopeQueryString", () => {
  it("serializes optional scope fields when present", () => {
    const query = scopeQueryString({
      namespaceId: "local",
      agentId: "coding-agent",
      userId: "user-1",
      projectId: "atlas",
    });

    expect(query).toBe("namespace_id=local&agent_id=coding-agent&user_id=user-1&project_id=atlas");
  });
});
