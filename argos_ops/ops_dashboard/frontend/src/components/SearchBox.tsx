import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";

export interface SearchBoxProps {
  /** Controlled search value (the committed/debounced query). */
  value: string;
  /** Called with the new query after debounce, or immediately on clear. */
  onChange: (q: string) => void;
  placeholder?: string;
  /** Debounce delay in ms before propagating typing to onChange. Default 250. */
  debounceMs?: number;
  /** Accessible label for the searchbox. Default "Rechercher". */
  ariaLabel?: string;
  className?: string;
}

/**
 * SearchBox — controlled, debounced search input (presentational).
 *
 * Keeps a local draft in sync with the controlled `value`, and only fires
 * `onChange` after `debounceMs` of inactivity. The clear button flushes
 * `onChange("")` immediately (bypassing the debounce).
 */
export function SearchBox({
  value,
  onChange,
  placeholder = "Rechercher…",
  debounceMs = 250,
  ariaLabel = "Rechercher",
  className,
}: SearchBoxProps): React.JSX.Element {
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  // Keep the latest onChange without re-arming the debounce timer.
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // Sync local draft when the controlled value changes externally.
  useEffect(() => {
    setDraft(value);
  }, [value]);

  // Debounce: propagate the draft to onChange after a quiet period.
  useEffect(() => {
    if (draft === value) return;
    const timer = setTimeout(() => {
      onChangeRef.current(draft);
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [draft, value, debounceMs]);

  const handleClear = (): void => {
    setDraft("");
    onChangeRef.current("");
    inputRef.current?.focus();
  };

  const hasValue = draft.length > 0;

  return (
    <div className={`relative inline-flex items-center ${className ?? ""}`}>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 h-4 w-4 text-argos-fg-tertiary"
      />
      <input
        ref={inputRef}
        type="search"
        role="searchbox"
        aria-label={ariaLabel}
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        className="w-full rounded-md border border-argos-border bg-argos-surface py-1.5 pl-8 pr-8 font-sans text-sm text-argos-fg placeholder:text-argos-fg-tertiary transition-colors duration-150 focus-visible:border-argos-info focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg [&::-webkit-search-cancel-button]:appearance-none"
      />
      {hasValue && (
        <button
          type="button"
          onClick={handleClear}
          aria-label="Effacer la recherche"
          className="absolute right-1.5 inline-flex h-5 w-5 items-center justify-center rounded text-argos-fg-tertiary transition-colors duration-150 hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
        >
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
