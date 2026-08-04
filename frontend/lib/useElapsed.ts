"use client";

import { useEffect, useState } from "react";

// Local elapsed-seconds timer for running-research UI. Kept inside the
// components that display it so a 250ms tick never re-renders the whole
// workspace tree. The value holds at the final elapsed time once `running`
// turns false, which lets callers render "Finished in …" after the fact.
export function useElapsed(running: boolean): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!running) return;
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed((Date.now() - start) / 1000);
    }, 250);
    return () => clearInterval(interval);
  }, [running]);

  return elapsed;
}
