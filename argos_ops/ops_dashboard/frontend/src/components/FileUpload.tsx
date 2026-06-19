import { useRef, useState, useCallback } from "react";
import type { ReactNode, DragEvent } from "react";
import Papa from "papaparse";
import { Upload, FileText, X, CheckCircle2, AlertCircle } from "lucide-react";

type Status = "idle" | "selected" | "error";

interface FileUploadProps {
  onFile: (file: File) => void;
  accept?: string;
  maxSizeMb?: number;
  parseCsv?: boolean;
  onCsvParsed?: (
    rows: Record<string, string>[],
    meta: { fields: string[]; rowCount: number },
  ) => void;
  label?: string;
  hint?: ReactNode;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} Mo`;
}

export function FileUpload({
  onFile,
  accept,
  maxSizeMb,
  parseCsv,
  onCsvParsed,
  label = "Déposez un fichier ou cliquez pour parcourir",
  hint,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState<string>("");
  const [fileSize, setFileSize] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [csvSummary, setCsvSummary] = useState<string>("");

  const limitMb = maxSizeMb ?? 5;

  const handleFile = useCallback(
    (file: File) => {
      setCsvSummary("");
      if (file.size > limitMb * 1024 * 1024) {
        setStatus("error");
        setErrorMsg(
          `Fichier trop volumineux (${formatSize(file.size)}). Maximum ${limitMb} Mo.`,
        );
        setFileName("");
        setFileSize(0);
        return;
      }

      setErrorMsg("");
      setFileName(file.name);
      setFileSize(file.size);
      setStatus("selected");
      onFile(file);

      if (parseCsv) {
        Papa.parse<Record<string, string>>(file, {
          header: true,
          skipEmptyLines: true,
          complete: (res) => {
            const rows = res.data;
            const fields = res.meta.fields ?? [];
            onCsvParsed?.(rows, { fields, rowCount: rows.length });
            setCsvSummary(
              `${rows.length} ligne${rows.length > 1 ? "s" : ""} · ${fields.length} colonne${fields.length > 1 ? "s" : ""}`,
            );
          },
        });
      }
    },
    [limitMb, onFile, parseCsv, onCsvParsed],
  );

  const openPicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const onDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
  }, []);

  const clear = useCallback(() => {
    setStatus("idle");
    setFileName("");
    setFileSize(0);
    setErrorMsg("");
    setCsvSummary("");
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  return (
    <div className="flex flex-col gap-2">
      <div
        role="button"
        tabIndex={0}
        aria-label={label}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openPicker();
          }
        }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={[
          "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed",
          "px-6 py-8 text-center transition-colors duration-150 cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg",
          dragging
            ? "border-argos-info bg-argos-info/15"
            : "border-argos-border bg-argos-surface hover:bg-argos-surface-2",
        ].join(" ")}
      >
        <Upload
          aria-hidden="true"
          className={dragging ? "h-6 w-6 text-argos-info" : "h-6 w-6 text-argos-fg-tertiary"}
        />
        <span className="text-sm text-argos-fg-secondary">{label}</span>
        {hint ? (
          <span className="text-xs text-argos-fg-tertiary">{hint}</span>
        ) : null}
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </div>

      {status === "error" ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2"
        >
          <AlertCircle
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0 text-argos-danger"
          />
          <span className="text-sm text-argos-danger">{errorMsg}</span>
        </div>
      ) : null}

      {status === "selected" ? (
        <div className="flex items-center gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2">
          <FileText
            aria-hidden="true"
            className="h-4 w-4 shrink-0 text-argos-fg-tertiary"
          />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-mono text-sm text-argos-fg">
              {fileName}
            </span>
            <span className="font-mono text-xs tabular-nums text-argos-fg-tertiary">
              {formatSize(fileSize)}
            </span>
            {csvSummary ? (
              <span className="mt-1 flex items-center gap-1.5 text-xs text-argos-healthy">
                <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                <span className="font-mono tabular-nums">{csvSummary}</span>
              </span>
            ) : null}
          </div>
          <button
            type="button"
            onClick={clear}
            aria-label={`Retirer le fichier ${fileName}`}
            className="shrink-0 rounded-md p-1 text-argos-fg-tertiary transition-colors duration-150 hover:bg-argos-surface-2 hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      ) : null}
    </div>
  );
}
