import Fuse from "fuse.js";
import { useMemo } from "react";

/**
 * Fuzzy full-text search hook backed by Fuse.js.
 *
 * Builds a memoized Fuse index over `items` keyed on `keys`, then memoizes the
 * filtered result for the given `query`. An empty (whitespace-only) query is a
 * no-op and returns the original `items` reference unchanged.
 *
 * @param items   The collection to search.
 * @param keys    Dotted paths into each item to index (Fuse key syntax).
 * @param query   The user-supplied search string.
 * @param options Optional tuning. `threshold` (0 = exact, 1 = match anything)
 *                defaults to 0.34.
 * @returns The matching subset of `items`, in Fuse relevance order.
 */
export function useFuzzySearch<T>(
  items: T[],
  keys: string[],
  query: string,
  options?: { threshold?: number },
): T[] {
  const threshold = options?.threshold ?? 0.34;
  const keysKey = keys.join(",");

  const fuse = useMemo(
    () =>
      new Fuse(items, {
        keys,
        threshold,
        ignoreLocation: true,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items, keysKey, threshold],
  );

  return useMemo(() => {
    if (query.trim() === "") {
      return items;
    }
    return fuse.search(query).map((r) => r.item);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fuse, items, query]);
}
