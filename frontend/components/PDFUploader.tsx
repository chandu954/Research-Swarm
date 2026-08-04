"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Check,
  ExternalLink,
  FileText,
  Loader2,
  Plus,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { uploadPDF, deleteDocument, getDocumentDownloadUrl } from "@/lib/api";
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

  const removeDocument = useCallback(
    async (id: string) => {
      try {
        await deleteDocument(id);
      } catch (err) {
        console.warn("Failed to delete document on server:", err);
      }
      onDocumentsChange(
        documents.filter((document) => document.document_id !== id),
      );
      onSelectionChange(
        selectedDocs.filter((documentId) => documentId !== id),
      );
    },
    [documents, selectedDocs, onDocumentsChange, onSelectionChange],
  );

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

      {documents.length === 0 && (
        <div className="mt-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              Recent files
            </p>
            <span className="rounded bg-white/[0.04] px-1.5 py-0.5 text-[7px] uppercase tracking-wide text-[var(--text-muted)]">
              Sample library
            </span>
          </div>
          <div className="space-y-1.5">
            {[
              { name: "paper-alignment-2025.pdf", meta: "indexed · 8 pages", ready: true },
              { name: "rag-survey.pdf", meta: "indexed · 24 pages", ready: true },
              { name: "notes.md", meta: "ready · 2.1 KB", ready: true },
            ].map((file) => (
              <div key={file.name} className="document-row">
                <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.03] text-emerald-300">
                  <FileText className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] font-medium text-[var(--text-primary)]">
                    {file.name}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1 text-[9px] text-[var(--text-muted)]">
                    <span className="text-emerald-400">✓</span>
                    {file.meta}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

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
            const name = document.original_filename || document.filename;
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
                      {name}
                    </span>
                    <span className="mt-0.5 flex items-center gap-1.5 text-[9px] text-[var(--text-muted)]">
                      {formatFileSize(document.size)}
                      {document.page_count && (
                        <>
                          <span>·</span>
                          <span>{document.page_count} pages</span>
                        </>
                      )}
                      <span>·</span>
                      <span className="text-emerald-400">
                        {document.status === "uploaded" ? "Ready" : document.status}
                      </span>
                    </span>
                    {document.auto_tags && document.auto_tags.length > 0 && (
                      <span className="mt-0.5 flex flex-wrap gap-1">
                        {document.auto_tags.slice(0, 3).map((tag: string) => (
                          <span key={tag} className="rounded bg-white/[0.04] px-1 py-0.5 text-[8px] text-[var(--text-muted)]">
                            {tag}
                          </span>
                        ))}
                      </span>
                    )}
                  </span>
                </button>

                <div className="flex items-center gap-1">
                  <a
                    href={getDocumentDownloadUrl(document.document_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="icon-button h-7 w-7 opacity-60 hover:text-cyan-300 hover:opacity-100"
                    aria-label={`View ${name}`}
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                  <button
                    type="button"
                    onClick={() => removeDocument(document.document_id)}
                    className="icon-button h-7 w-7 opacity-60 hover:text-rose-300 hover:opacity-100"
                    aria-label={`Remove ${name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}
