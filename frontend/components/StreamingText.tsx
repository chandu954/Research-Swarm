"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface StreamingTextProps {
  content: string;
  speed?: number;
  onComplete?: () => void;
}

export default function StreamingText({ content, speed = 15, onComplete }: StreamingTextProps) {
  const [displayed, setDisplayed] = useState("");
  const indexRef = useRef(0);
  const doneRef = useRef(false);

  useEffect(() => {
    indexRef.current = 0;
    setDisplayed("");
    doneRef.current = false;
  }, [content]);

  useEffect(() => {
    if (doneRef.current) return;
    if (indexRef.current >= content.length) {
      doneRef.current = true;
      onComplete?.();
      return;
    }

    const timer = setInterval(() => {
      if (indexRef.current < content.length) {
        setDisplayed(content.slice(0, indexRef.current + 1));
        indexRef.current++;
      } else {
        clearInterval(timer);
        doneRef.current = true;
        onComplete?.();
      }
    }, speed);

    return () => clearInterval(timer);
  }, [content, speed, onComplete]);

  if (displayed.length === 0 && content.length > 0) return null;

  return (
    <article className="prose-custom prose-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {displayed || content}
      </ReactMarkdown>
      {indexRef.current < content.length && (
        <span className="typing-animation text-primary ml-0.5" />
      )}
    </article>
  );
}
