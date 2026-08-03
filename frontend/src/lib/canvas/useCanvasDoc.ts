import { useCallback, useEffect, useRef, useState } from "react";
import type { CanvasElement } from "@/lib/api/types";
import { api, subscribe } from "@/lib/api/api";

export type SaveState = "saved" | "saving" | "pending" | "error";

/**
 * Local collaboration document. Optimistic local edits + debounced autosave
 * through the backend API, plus WebSocket fan-out of remote updates.
 */
export function useCanvasDoc(sessionId: string, actorId: string, canEdit: boolean) {
  const [elements, setElements] = useState<CanvasElement[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const history = useRef<{ past: CanvasElement[][]; future: CanvasElement[][] }>({
    past: [],
    future: [],
  });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef<CanvasElement[]>([]);
  const remote = useRef(false);

  useEffect(() => {
    let alive = true;
    api.getCanvas(sessionId).then((doc) => {
      if (!alive) return;
      latest.current = doc.elements;
      setElements(doc.elements);
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, [sessionId]);

  useEffect(
    () =>
      subscribe(sessionId, (msg) => {
        if (msg.type === "document_update" && msg.actor !== actorId) {
          remote.current = true;
          latest.current = msg.elements;
          setElements(msg.elements);
        }
      }),
    [sessionId, actorId],
  );

  const flush = useCallback(() => {
    setSaveState("saving");
    api
      .saveCanvas(sessionId, latest.current, actorId)
      .then(() => setSaveState("saved"))
      .catch(() => setSaveState("error"));
  }, [sessionId, actorId]);

  const scheduleSave = useCallback(() => {
    setSaveState("pending");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(flush, 900);
  }, [flush]);

  /** Commit a persistent operation. */
  const commit = useCallback(
    (updater: (prev: CanvasElement[]) => CanvasElement[], recordHistory = true) => {
      if (!canEdit) return;
      setElements((prev) => {
        const next = updater(prev);
        if (next === prev) return prev;
        if (recordHistory) {
          history.current.past.push(prev);
          if (history.current.past.length > 100) history.current.past.shift();
          history.current.future = [];
        }
        latest.current = next;
        scheduleSave();
        return next;
      });
    },
    [canEdit, scheduleSave],
  );

  const undo = useCallback(() => {
    if (!canEdit) return;
    setElements((prev) => {
      const past = history.current.past.pop();
      if (!past) return prev;
      history.current.future.push(prev);
      latest.current = past;
      scheduleSave();
      return past;
    });
  }, [canEdit, scheduleSave]);

  const redo = useCallback(() => {
    if (!canEdit) return;
    setElements((prev) => {
      const next = history.current.future.pop();
      if (!next) return prev;
      history.current.past.push(prev);
      latest.current = next;
      scheduleSave();
      return next;
    });
  }, [canEdit, scheduleSave]);

  return { elements, setElements, commit, undo, redo, loaded, saveState, flush };
}
