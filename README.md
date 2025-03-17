# Trading Bot Backend

This backend service is built using FastAPI, SQLAlchemy, and SQLite. It exposes an API endpoint for storing API keys for various exchanges (Binance, BitMart, Coinbase, Bybit, Gate.io). The data is stored in a local SQLite database.

---
## Features

- **API Endpoint:** Accepts API keys and secrets for exchanges.
- **Database:** Uses SQLite (`trading_bot.db`) to store API key records.
- **Framework:** Built with FastAPI for quick development and testing.
---
## Getting Started

#### Prerequisites

- Python 3.8+
- [pip](https://pip.pypa.io/en/stable/)

#### Installation

1. **Clone the Repository:**

```bash
git clone https://github.com/devopslp/bruno-bot.git
cd bruno-bot/backend
```
2.	**Create & Activate a Virtual Environment:**

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3.	**Install Dependencies:**

`pip install -r requirements.txt`



#### Running the Server

When you run main.py, it will automatically initialize the SQLite database (if it doesn’t exist) and create the required tables.

#### To start the server:
Simply run `python src/main.py`
Or, using uvicorn directly: `uvicorn src.main:app --reload`

The server will run on `http://0.0.0.0:8000`

---
## API Endpoints

### 📝 Add API Key
- **Endpoint:** /api-keys
-	**Method:** POST

- **Testing:**   You can test the endpoint using tools like [Postman](https://www.postman.com/) or `curl`. For example:


```bash
curl -X POST "http://0.0.0.0:8000/api-keys/" \
      -H "Content-Type: application/json" \
      -d '{
            "exchange": "Binance",
            "api_key": "your_api_key",
            "api_secret": "your_api_secret",
            "balance": 1000.0,
            "leverage": 10.0
          }'
```

**Request Body Example:**

```json
{
  "exchange": "Binance",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret"
}
```

**Successful Response (Status Code 200):**

The response will include the created API key record:
```json
{
  "id": 1,
  "exchange": "Binance",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret"
}
```

Error Response (Status Code 400):

If an API key for the given exchange already exists, you’ll receive an error:

```json
{
  "detail": "API key for this exchange already exists."
}
```

### 🔎 Get API Key
• **Endpoint:** `/api-keys/{exchange}`
• **Method:** GET

- **Testing:**  
  You can test the endpoint using tools like [Postman](https://www.postman.com/) or `curl`. For example:

    ```bash
    curl -X GET "http://0.0.0.0:8000/api-keys/binance"
    ```

**Successful Response (Status Code 200):**

The response will return the stored API key record:

```json
{
  "id": 1,
  "exchange": "binance",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "balance": 1000.0,
  "leverage": 10.0
}
```
Error Response (Status Code 404):

If no API key is found for the given exchange, the response will be:
```json

{
  "detail": "No API key found for this exchange."
}
```
### Update API Key

- Endpoint: /api-keys/{exchange}
- Method: PUT

-	**Testing:** You can test the endpoint using tools like Postman or curl. For example:

```bash
curl -X PUT "http://0.0.0.0:8000/api-keys/binance" \
    -H "Content-Type: application/json" \
    -d '{
            "api_key": "new_api_key",
            "api_secret": "new_api_secret",
            "balance": 2000.0,
            "leverage": 5.0
        }'
```

**Request Body Example:**

```json
{
  "api_key": "new_api_key",
  "api_secret": "new_api_secret",
  "balance": 2000.0,
  "leverage": 5.0
}
```

**Successful Response (Status Code 200):**

The response will return the updated API key record:

```json
{
  "id": 1,
  "exchange": "binance",
  "api_key": "new_api_key",
  "api_secret": "new_api_secret",
  "balance": 2000.0,
  "leverage": 5.0
}
```

**Error Response (Status Code 404):**

If the exchange does not have an API key stored, the response will be:

```json
{
  "detail": "No API key found for this exchange."
}
```

### 🛑 Delete API Key

- Endpoint: /api-keys/{exchange}
- Method: DELETE

- **Testing:** You can test the endpoint using tools like Postman or curl. For example:

```bash
curl -X DELETE "http://0.0.0.0:8000/api-keys/binance"
```


**Successful Response (Status Code 200):**

If the API key was deleted successfully:
```json
{
  "message": "API key for binance deleted successfully."
}
```

**Error Response (Status Code 404):**

If no API key exists for the given exchange:
```json
{
  "detail": "No API key found for this exchange."
}
```

### Start Grid Bot
• **Endpoint:** `/grid-bot/start`  
• **Method:** POST

- **Testing:**  You can test this endpoint using `curl`.

```bash
curl -X POST "http://0.0.0.0:8000/grid-bot/start" \
      -H "Content-Type: application/json" \
      -d '{
            "tp_percent": 2.5,
            "sl_percent": 1.0,
            "exchanges": ["Binance", "Gate.io"]
          }'
```

**Request Body Example:**

```json
{
  "tp_percent": 2.5,
  "sl_percent": 1.0,
  "exchanges": ["Binance", "Gate.io"]
}
```

**Successful Response (Status Code 200):**

```json
{
  "message": "Grid bot started",
  "tp_percent": 2.5,
  "sl_percent": 1.0,
  "exchanges": ["Binance", "Gate.io"]
}
```


### Stop Grid Bot

- **Endpoint:** `/grid-bot/stop`
- **Method:** **POST**
-	Testing: You can test the endpoint using tools like Postman or curl. For example:

```bash
curl -X POST "http://0.0.0.0:8000/grid-bot/stop"
```

**Successful Response (Status Code 200):**
The response will confirm that the grid bot has been stopped:
```json
{
  "message": "Grid bot stopped"
}
```

### Check Grid Bot Status
• **Endpoint:** `/grid-bot/status`  
• **Method:** GET

- **Testing:**  
  You can test this endpoint using tools like [Postman](https://www.postman.com/) or `curl`. For example:

    ```bash
    curl -X GET "http://0.0.0.0:8000/grid-bot/status"
    ```

**Successful Response (Status Code 200):**

The response will include the current status of the grid bot:

- If the grid bot is running:

    ```json
    {
      "status": "running"
    }
    ```

- If the grid bot is stopped:

    ```json
    {
      "status": "stopped"
    }
    ```

---

### Notes

- **Database Initialization:**  
  The call to `models.Base.metadata.create_all(bind=engine)` in `main.py` ensures that when the server starts, the SQLite database is initialized (if not already present) and the required tables are created.

