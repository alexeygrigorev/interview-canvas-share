import { useCallback, useEffect, useRef, useState } from "react";
import type { Participant } from "@/lib/api/types";
import { publish, subscribe } from "@/lib/api/api";

/** Ephemeral room presence synchronized through the realtime gateway. */
export function useRoomPresence(sessionId: string, me: Participant | null) {
  const [peers, setPeers] = useState<Record<string, Participant>>({});
  const last = useRef(0);

  useEffect(() => {
    if (!me) return;
    setPeers((p) => ({ ...p, [me.id]: me }));
    publish({ type: "presence_update", sessionId, participant: me });
    const beat = setInterval(
      () => publish({ type: "presence_update", sessionId, participant: me }),
      4000,
    );
    return () => {
      clearInterval(beat);
      publish({ type: "presence_leave", sessionId, participantId: me.id });
    };
  }, [sessionId, me]);

  useEffect(
    () =>
      subscribe(sessionId, (msg) => {
        if (msg.type === "presence_update") {
          setPeers((prev) => ({
            ...prev,
            [msg.participant.id]: { ...msg.participant, cursor: msg.cursor ?? prev[msg.participant.id]?.cursor ?? null },
          }));
        }
        if (msg.type === "presence_leave") {
          setPeers((prev) => {
            const next = { ...prev };
            delete next[msg.participantId];
            return next;
          });
        }
      }),
    [sessionId],
  );

  const sendCursor = useCallback(
    (cursor: { x: number; y: number } | null) => {
      if (!me) return;
      const now = Date.now();
      if (now - last.current < 60) return;
      last.current = now;
      publish({ type: "presence_update", sessionId, participant: me, cursor });
    },
    [sessionId, me],
  );

  return { peers: Object.values(peers), sendCursor };
}
