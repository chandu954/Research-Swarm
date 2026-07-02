"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Check,
  FileText,
  Loader2,
  Plus,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { uploadPDF } from "@/lib/api";
import type { UploadedDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

interface PDFUploaderProps {
  documents: UploadedDocument[];
  onDocumentsChange: (documents: UploadedDocument[]) => void;
  selectedDocs: string[];
  onSelectionChange: (ids: string[]) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function PDFUploader({
  documents,
  onDocumentsChange,
  selectedDocs,
  onSelectionChange,
}: PDFUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string>();

  const handleUpload = useCallback(
    async (files: File[]) => {
      const pdfs = files.filter((file) =>
        file.name.toLowerCase().endsWith(".pdf"),
      );
      if (pdfs.length === 0) {
        setUploadError("Choose one or more PDF files.");
        return;
      }

      setUploading(true);
      setUploadError(undefined);
      try {
        const uploaded = await Promise.all(pdfs.map((file) => uploadPDF(file)));
        onDocumentsChange([...uploaded, ...documents]);
        onSelectionChange([
          ...uploaded.map((document) => document.document_id),
          ...selectedDocs,
        ]);
      } catch (error) {
        setUploadError(
          error instanceof Error ? error.message : "The upload failed.",
        );
      } finally {
        setUploading(false);
      }
    },
    [documents, onDocumentsChange, onSelectionChange, selectedDocs],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLLabelElement>) => {
      event.preventDefault();
      setDragOver(false);
      void handleUpload(Array.from(event.dataTransfer.files));
    },
    [handleUpload],
  );

  const toggleDocument = (id: string) => {
    onSelectionChange(
      selectedDocs.includes(id)
        ? selectedDocs.filter((documentId) => documentId !== id)
        : [...selectedDocs, id],
    );
  };

  const removeDocument = (id: string) => {
    onDocumentsChange(
      documents.filter((document) => document.document_id !== id),
    );
    onSelectionChange(
      selectedDocs.filter((documentId) => documentId !== id),
    );
  };

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Documents
            </h2>
          </div>
          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
            {documents.length > 0
              ? `${selectedDocs.length} of ${documents.length} selected`
              : "Add evidence to your research"}
          </p>
        </div>
        {documents.length > 0 && (
          <label htmlFor="pdf-upload" className="add-file-button">
            <Plus className="h-3 w-3" />
            Add files
          </label>
        )}
      </div>

      <label
        htmlFor="pdf-upload"
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          "upload-zone",
          dragOver && "border-emerald-400/35 bg-emerald-500/[0.06]",
          documents.length > 0 && "upload-zone-compact",
        )}
      >
        <input
          id="pdf-upload"
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="sr-only"
          onChange={(event) => {
            if (event.target.files) {
              void handleUpload(Array.from(event.target.files));
              event.target.value = "";
            }
          }}
        />
        {uploading ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />
            <span>Uploading and preparing files...</span>
          </>
        ) : (
          <>
            <UploadCloud className="h-5 w-5 text-emerald-400" />
            <span>
              {documents.length > 0
                ? "Drop more PDFs here"
                : "Drop PDFs here or click to browse"}
            </span>
            {documents.length === 0 && (
              <small>Multiple files supported · 50 MB each</small>
            )}
          </>
        )}
      </label>

      {uploadError && (
        <div className="mt-2 flex gap-2 rounded-lg border border-rose-400/15 bg-rose-500/[0.05] p-2 text-[10px] text-rose-300">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="line-clamp-2">{uploadError}</span>
        </div>
      )}

      <div className="mt-3 max-h-[260px] space-y-2 overflow-y-auto">
        <AnimatePresence initial={false}>
          {documents.map((document) => {
            const selected = selectedDocs.includes(document.document_id);
            return (
              <motion.div
                key={document.document_id}
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className={cn(
                  "document-row",
                  selected && "border-emerald-400/15 bg-emerald-500/[0.035]",
                )}
              >
                <button
                  type="button"
                  onClick={() => toggleDocument(document.document_id)}
                  className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                  aria-pressed={selected}
                >
                  <span
                    className={cn(
                      "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg border",
                      selected
                        ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-300"
                        : "border-white/[0.07] bg-white/[0.03] text-[var(--text-muted)]",
                    )}
                  >
                    {selected ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <FileText className="h-3.5 w-3.5" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[11px] font-medium text-[var(--text-primary)]">
                      {document.filename}
                    </span>
                    <span className="mt-0.5 flex items-center gap-1.5 text-[9px] text-[var(--text-muted)]">
                      {formatFileSize(document.size)}
                      <span>·</span>
                      <span className="text-emerald-400">
                        {document.status === "uploaded" ? "Ready" : document.status}
                      </span>
                    </span>
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => removeDocument(document.document_id)}
                  className="icon-button h-7 w-7 opacity-60 hover:text-rose-300 hover:opacity-100"
                  aria-label={`Remove ${document.filename}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}
