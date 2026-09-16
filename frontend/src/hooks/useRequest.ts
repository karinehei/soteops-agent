"use client";

import { useCallback, useEffect, useState } from "react";

import type { RequestOut } from "@/lib/api-types";
import { ApiError, api } from "@/lib/api";

const POLL_STATUSES = new Set(["submitted", "preparing", "forwarding"]);

export function useRequest(requestId: string) {
  const [request, setRequest] = useState<RequestOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const data = await api.getRequest(requestId);
      setRequest(data);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Pyynnön lataus epäonnistui");
      return null;
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await api.getRequest(requestId);
        if (!cancelled) {
          setRequest(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Pyynnön lataus epäonnistui");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  useEffect(() => {
    if (!request || !POLL_STATUSES.has(request.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void reload();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [request, reload]);

  return { request, loading, error, reload, setRequest };
}
