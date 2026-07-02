"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { getMemriseClient } from "@/lib/api";
import { captureMessage } from "@/services/capture";

const DEFAULT_MESSAGE =
  "Atlas used npm before, but we now use pnpm. Never edit its generated lockfile manually.";

export function usePlaygroundCapture() {
  const client = getMemriseClient();
  const [message, setMessage] = useState(DEFAULT_MESSAGE);

  const capture = useMutation({
    mutationFn: () => captureMessage(client, message),
  });

  return {
    message,
    setMessage,
    capture,
  };
}
