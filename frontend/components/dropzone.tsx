"use client";

import * as React from "react";
import { UploadCloud, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DropzoneProps {
  accept: string;
  onFile: (file: File | null) => void;
  hint?: string;
  file?: File | null;
  disabled?: boolean;
}

export function Dropzone({ accept, onFile, hint, file, disabled }: DropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [drag, setDrag] = React.useState(false);

  function pick() {
    inputRef.current?.click();
  }

  function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    onFile(e.target.files?.[0] ?? null);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  }

  if (file) {
    return (
      <div className="flex items-center justify-between rounded-[8px] border border-brand-200 bg-brand-50/60 px-3 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink">{file.name}</p>
          <p className="text-2xs text-ink-subtle">{(file.size / 1024).toFixed(1)} KB</p>
        </div>
        <button
          type="button"
          onClick={() => onFile(null)}
          className="rounded-full p-1 text-ink-subtle hover:bg-brand-100 hover:text-ink"
          aria-label="Quitar archivo"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={pick}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      disabled={disabled}
      className={cn(
        "flex w-full flex-col items-center justify-center gap-2 rounded-[10px] border border-dashed border-line px-4 py-8 text-center transition-colors",
        "hover:border-brand-400 hover:bg-brand-50/40",
        drag && "border-brand-600 bg-brand-50",
        disabled && "cursor-not-allowed opacity-60"
      )}
    >
      <UploadCloud className={cn("h-6 w-6", drag ? "text-brand-600" : "text-ink-subtle")} />
      <div>
        <p className="text-sm font-medium text-ink">Arrastra el archivo o haz clic</p>
        {hint && <p className="mt-0.5 text-2xs text-ink-subtle">{hint}</p>}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={onChange}
        disabled={disabled}
      />
    </button>
  );
}
