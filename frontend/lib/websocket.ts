const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PresenceUser {
  userId: string;
  name: string;
  status: "online" | "away" | "offline";
  lastSeen?: number;
}

export interface ChatMessage {
  id: string;
  userId: string;
  userName: string;
  content: string;
  timestamp: number;
}

export interface TypingUser {
  userId: string;
  name: string;
}

export type WSCallback = {
  onPresence?: (users: PresenceUser[]) => void;
  onChatMessage?: (msg: ChatMessage) => void;
  onChatHistory?: (messages: ChatMessage[]) => void;
  onTyping?: (users: TypingUser[]) => void;
  onResearchStart?: (payload: { userId: string; userName: string; taskId: string; query: string }) => void;
  onResearchLog?: (payload: { taskId: string; log: unknown }) => void;
  onResearchComplete?: (payload: { taskId: string; userId: string }) => void;
  onDocumentAdded?: (payload: { document: unknown }) => void;
  onDocumentRemoved?: (payload: { documentId: string }) => void;
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

  send(type: string, payload?: Record<string, unknown>) {
    if (this.ws?.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type, payload }));
  }

  sendChat(content: string) {
    this.send("chat:send", { content });
  }

  sendTyping(isTyping: boolean) {
    this.send("typing", { isTyping });
  }

  private _connect() {
    if (!this.currentWorkspaceId || !this.currentToken) return;
    const protocol = API_URL.startsWith("https") ? "wss" : "ws";
    const base = API_URL.replace(/^https?:\/\//, "");
    const url = `${protocol}://${base}/ws/workspace/${this.currentWorkspaceId}`;

    try {
      this.ws = new WebSocket(url, ["research-swarm", this.currentToken]);
      this.ws.onopen = () => {
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };
      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this._route(msg);
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

  private _route(msg: { type: string; payload?: unknown; users?: PresenceUser[]; messages?: ChatMessage[] }) {
    switch (msg.type) {
      case "presence":
        this.callbacks.onPresence?.(msg.users || []);
        break;
      case "chat:message":
        this.callbacks.onChatMessage?.(msg.payload as ChatMessage);
        break;
      case "chat:history":
        this.callbacks.onChatHistory?.((msg.payload as { messages: ChatMessage[] })?.messages || []);
        break;
      case "typing":
        this.callbacks.onTyping?.((msg.payload as { typingUsers: TypingUser[] })?.typingUsers || []);
        break;
      case "research:start":
        this.callbacks.onResearchStart?.(msg.payload as { userId: string; userName: string; taskId: string; query: string });
        break;
      case "research:log":
        this.callbacks.onResearchLog?.(msg.payload as { taskId: string; log: unknown });
        break;
      case "research:complete":
        this.callbacks.onResearchComplete?.(msg.payload as { taskId: string; userId: string });
        break;
      case "document:added":
        this.callbacks.onDocumentAdded?.(msg.payload as { document: unknown });
        break;
      case "document:removed":
        this.callbacks.onDocumentRemoved?.(msg.payload as { documentId: string });
        break;
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
