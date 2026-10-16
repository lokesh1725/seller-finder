import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "seller_finder_recent_searches";
const MAX_ITEMS = 8;

function read() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function useRecentSearches() {
  const [recent, setRecent] = useState(read);

  const add = useCallback((query) => {
    const value = String(query || "").trim();
    if (!value) return;
    setRecent((prev) => {
      const next = [value, ...prev.filter((q) => q.toLowerCase() !== value.toLowerCase())].slice(
        0,
        MAX_ITEMS
      );
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* storage may be unavailable */
      }
      return next;
    });
  }, []);

  const remove = useCallback((query) => {
    setRecent((prev) => {
      const next = prev.filter((q) => q !== query);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setRecent([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    setRecent(read());
  }, []);

  return { recent, add, remove, clear };
}
