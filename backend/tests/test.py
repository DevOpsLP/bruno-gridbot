import websocket
import json
import time
import hmac
import hashlib

API_KEY = "zjy40hlm2ZwNOJcmbraOMTSuuARFwCXMQpNQ2aQAUB0UtOrFOoFbbtHkQXRLeuf5"
API_SECRET = "hHu7Q9EltjzD3YlNjTvSJnZ95bd1N0AycPp5t3NhnuUOgoyXtsQaOSoeNnQRqYke"

def generate_signature(api_key, api_secret, timestamp):
    payload = f"apiKey={api_key}&timestamp={timestamp}"
    signature = hmac.new(
        api_secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def on_message(ws, message):
    print("Received:", message)
    try:
        data = json.loads(message)
        if 'ping' in data:
            pong_response = {"pong": data["ping"]}
            ws.send(json.dumps(pong_response))
            print("Sent pong:", pong_response)
    except Exception as e:
        print("Message handling error:", e)

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    print(f"Closed connection ({close_status_code}): {close_msg}")

def on_open(ws):
    print("Connection opened!")
    timestamp = int(time.time() * 1000)
    signature = generate_signature(API_KEY, API_SECRET, timestamp)

    logon_msg = {
        "id": "login_request",
        "method": "session.logon",
        "params": {
            "apiKey": API_KEY,
            "signature": signature,
            "timestamp": timestamp
        }
    }

    ws.send(json.dumps(logon_msg))
    print("Sent logon:", logon_msg)

if __name__ == "__main__":
    websocket.enableTrace(True)
    ws_url = "wss://testnet.binance.vision/ws-api/v3"  # Use testnet for safety
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever(ping_interval=20, ping_timeout=10)