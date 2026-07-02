import { describe, expect, it } from "vitest";
import { MemoryClientError } from "../src/errors.js";

describe("MemoryClientError", () => {
  it("exposes status code and structured error code", () => {
    const error = new MemoryClientError("bad request", {
      status: 422,
      code: "validation_error",
      requestId: "req_1",
    });
    expect(error.status).toBe(422);
    expect(error.code).toBe("validation_error");
    expect(error.requestId).toBe("req_1");
  });
});
