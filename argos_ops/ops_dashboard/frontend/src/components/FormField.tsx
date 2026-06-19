import type { ReactNode } from "react";

interface FormFieldProps {
  label: string;
  htmlFor?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}

export function FormField({
  label,
  htmlFor,
  required = false,
  error,
  hint,
  children,
  className,
}: FormFieldProps) {
  return (
    <div className={`space-y-1.5${className ? ` ${className}` : ""}`}>
      <label
        htmlFor={htmlFor}
        className="block text-sm font-medium text-argos-fg"
      >
        {label}
        {required ? (
          <>
            <span className="ml-0.5 text-argos-danger" aria-hidden="true">
              *
            </span>
            <span className="sr-only"> requis</span>
          </>
        ) : null}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-xs text-argos-danger">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-argos-fg-tertiary">{hint}</p>
      ) : null}
    </div>
  );
}
