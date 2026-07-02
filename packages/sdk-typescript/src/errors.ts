export class MemoryClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(
    message: string,
    options: { status: number; code: string; requestId?: string | null },
  ) {
    super(message);
    this.name = "MemoryClientError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId ?? null;
  }
}
