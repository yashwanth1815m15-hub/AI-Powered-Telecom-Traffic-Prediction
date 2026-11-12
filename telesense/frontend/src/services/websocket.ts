/**
 * TeleSense Real-Time WebSocket Subscriber
 * Connects to live stream and notifies UI components on every 10-minute simulated tick.
 */

type ListenerCallback = (data: any) => void;

class WebSocketClient {
  private socket: WebSocket | null = null;
  private listeners: Set<ListenerCallback> = new Set();
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  public isConnected: boolean = false;

  public connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.isConnected = true;
        this.startHeartbeat();
        this.notify({ type: 'STATUS_CHANGE', isConnected: true });
      };

      this.socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.notify(msg);
        } catch (e) {
          console.warn('Failed to parse WebSocket message:', e);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        this.stopHeartbeat();
        this.notify({ type: 'STATUS_CHANGE', isConnected: false });
        this.scheduleReconnect();
      };

      this.socket.onerror = () => {
        this.socket?.close();
      };
    } catch (e) {
      this.scheduleReconnect();
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'PING' }));
      }
    }, 15000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  public subscribe(callback: ListenerCallback): () => void {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  private notify(data: any) {
    this.listeners.forEach((listener) => {
      try {
        listener(data);
      } catch (err) {
        console.error('Error in listener callback:', err);
      }
    });
  }
}

export const wsClient = new WebSocketClient();

