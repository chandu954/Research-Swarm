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
  private currentWorkspaceId: string | null = null;
  private currentToken: string | null = null;
  private isDisconnecting = false;

  connect(workspaceId: string, token: string, callbacks: WSCallback) {
    this.disconnect();
    this.currentWorkspaceId = workspaceId;
    this.currentToken = token;
    this.callbacks = callbacks;
    this.isDisconnecting = false;
    this._connect();
  }

  private _connect() {
    if (!this.currentWorkspaceId || !this.currentToken) return;
    const protocol = API_URL.startsWith("https") ? "wss" : "ws";
    const base = API_URL.replace(/^https?:\/\//, "");
    const url = `${protocol}://${base}/ws/workspace/${this.currentWorkspaceId}?token=${this.currentToken}`;

    try {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => {
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
        if (!this.isDisconnecting) {
          this.reconnectTimer = setTimeout(() => this._connect(), 5000);
        }
      };
    } catch (err) {
      if (!this.isDisconnecting) {
        this.reconnectTimer = setTimeout(() => this._connect(), 5000);
      }
    }
  }

  disconnect() {
    this.isDisconnecting = true;
    this.currentWorkspaceId = null;
    this.currentToken = null;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}

export const collaborationClient = new CollaborationClient();
