const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PresenceUser {
  userId: string;
  name: string;
  status: "online" | "away" | "offline";
  lastSeen?: number;
}

type WSCallback = {
  onPresence?: (users: PresenceUser[]) => void;
  onMessage?: (msg: unknown) => void;
  onError?: (err: Event) => void;
};

export class CollaborationClient {
  private ws: WebSocket | null = null;
  private callbacks: WSCallback = {};
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(workspaceId: string, token: string, callbacks: WSCallback) {
    this.callbacks = callbacks;
    const protocol = API_URL.startsWith("https") ? "wss" : "ws";
    const base = API_URL.replace(/^https?:\/\//, "");
    const url = `${protocol}://${base}/ws/workspace/${workspaceId}?token=${token}`;

    try {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => {
        console.log("[WS] Connected to workspace", workspaceId);
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };
      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "presence") {
            this.callbacks.onPresence?.(msg.users);
          } else {
            this.callbacks.onMessage?.(msg);
          }
        } catch { /* skip malformed */ }
      };
      this.ws.onerror = (err) => this.callbacks.onError?.(err);
      this.ws.onclose = () => {
        console.log("[WS] Disconnected, reconnecting in 5s");
        this.reconnectTimer = setTimeout(() => this.connect(workspaceId, token, callbacks), 5000);
      };
    } catch (err) {
      console.error("[WS] Connection failed", err);
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}

export const collaborationClient = new CollaborationClient();
