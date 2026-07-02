"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { getMemriseClient } from "@/lib/api";
import {
  pickPrimaryMemoryVersionId,
  retrieveMemories,
  submitHelpfulFeedback,
} from "@/services/retrieve";

const DEFAULT_QUERY = "How should I install dependencies for Atlas?";

export function usePlaygroundRecall() {
  const client = getMemriseClient();
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [retrievalId, setRetrievalId] = useState<string | null>(null);
  const [memoryVersionId, setMemoryVersionId] = useState<string | null>(null);

  const retrieve = useMutation({
    mutationFn: () => retrieveMemories(client, query),
    onSuccess: (data) => {
      setRetrievalId(data.retrieval_id);
      setMemoryVersionId(pickPrimaryMemoryVersionId(data));
    },
  });

  const feedback = useMutation({
    mutationFn: () => {
      if (!retrievalId || !memoryVersionId) {
        throw new Error("retrieve memory before feedback");
      }
      return submitHelpfulFeedback(client, retrievalId, memoryVersionId);
    },
  });

  return {
    query,
    setQuery,
    retrievalId,
    retrieve,
    feedback,
  };
}
