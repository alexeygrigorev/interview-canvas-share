import { useCallback, useEffect, useRef, useState } from "react";
import type { CanvasElement } from "@/lib/api/types";
import { api, publish, subscribe } from "@/lib/api/api";

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

  const publishUpdate = useCallback(
    (next: CanvasElement[]) => {
      latest.current = next;
      setElements(next);
      publish({
        type: "document_update",
        sessionId,
        elements: next,
        actor: actorId,
      });
      scheduleSave();
    },
    [actorId, scheduleSave, sessionId],
  );

  /** Commit a persistent operation. */
  const commit = useCallback(
    (updater: (prev: CanvasElement[]) => CanvasElement[], recordHistory = true) => {
      if (!canEdit) return;
      const prev = latest.current;
      const next = updater(prev);
      if (next === prev) return;
      if (recordHistory) {
        history.current.past.push(prev);
        if (history.current.past.length > 100) history.current.past.shift();
        history.current.future = [];
      }
      publishUpdate(next);
    },
    [canEdit, publishUpdate],
  );

  const undo = useCallback(() => {
    if (!canEdit) return;
    const past = history.current.past.pop();
    if (!past) return;
    history.current.future.push(latest.current);
    publishUpdate(past);
  }, [canEdit, publishUpdate]);

  const redo = useCallback(() => {
    if (!canEdit) return;
    const next = history.current.future.pop();
    if (!next) return;
    history.current.past.push(latest.current);
    publishUpdate(next);
  }, [canEdit, publishUpdate]);

  return { elements, setElements, commit, undo, redo, loaded, saveState, flush };
}
