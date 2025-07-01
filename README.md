# GitHub Activity Monitor

A Flask-based web application to monitor GitHub repository events (push, pull request, merge) in real-time, storing them in MongoDB and displaying them in a modern UI.

## Features
- Receives GitHub webhook events (push, pull request, merge)
- Stores events in MongoDB
- Modern, responsive UI to view recent events
- REST API to fetch latest events
- Health check endpoint

## Setup Instructions

### 1. Clone the Repository
```sh
git clone <your-repo-url>
cd webhook-repo
```

### 2. Install Dependencies
It is recommended to use a virtual environment.
```sh
python -m venv venv
venv\Scripts\activate  # On Windows
# Or
source venv/bin/activate  # On macOS/Linux

pip install -r requirements.txt
```

### 3. Configure MongoDB
- By default, the app connects to MongoDB at `mongodb://localhost:27017/`.
- To use a different MongoDB URI, set the `MONGO_URI` environment variable:
  ```sh
  set MONGO_URI=mongodb://<host>:<port>/  # On Windows
  export MONGO_URI=mongodb://<host>:<port>/  # On macOS/Linux
  ```

### 4. Run the Application
```sh
python app.py
```
The app will be available at [http://localhost:5000](http://localhost:5000).

### 5. Expose Localhost to the Internet (for GitHub Webhooks)
To receive webhooks from GitHub, you need a public URL. Use [ngrok](https://ngrok.com/):

```sh
ngrok http 5000
```
- Copy the HTTPS URL provided by ngrok (e.g., `https://abcd1234.ngrok.io`).
- In your GitHub repository, go to **Settings > Webhooks > Add webhook**:
  - **Payload URL:** `https://abcd1234.ngrok.io/webhook`
  - **Content type:** `application/json`
  - **Events:** Choose individual events or "Just the push event" (recommended: push, pull request)
  - **Secret:** (optional)

## API Documentation

### 1. `POST /webhook`
Receives GitHub webhook events. Handles `push`, `pull_request`, and `merge` (when a PR is closed and merged).

- **Headers:**
  - `X-GitHub-Event`: Event type (e.g., `push`, `pull_request`)
- **Body:**
  - JSON payload from GitHub
- **Response:**
  - `200 OK` with status and inserted event ID, or status ignored if event is not relevant
  - `400 Bad Request` if no payload
  - `500 Internal Server Error` on failure

### 2. `GET /api/events`
Returns the latest 10 events, sorted by timestamp (most recent first).

- **Response:**
  - `200 OK` with JSON array of events:
    ```json
    [
      {
        "_id": "...",
        "action": "push|pull_request|merge",
        "author": "...",
        "from_branch": "...",  // null for push
        "to_branch": "...",
        "timestamp": "2025-07-01T12:34:56.789Z",
        "request_id": "..."
      },
      ...
    ]
    ```
  - `500 Internal Server Error` on failure

### 3. `GET /health`
Health check endpoint.
- **Response:**
  - `200 OK` with status and current timestamp
    ```json
    { "status": "healthy", "timestamp": "2025-07-01T12:34:56.789Z" }
    ```

### 4. `/`
Main UI page. Displays recent events in a modern dashboard.
Visit the webhook receiver application at [YOUR_WEBHOOK_APP_URL] to see real-time updates of repository activity.

## Event Types Stored
- **push**: `{ action, author, to_branch, timestamp, request_id }`
- **pull_request**: `{ action, author, from_branch, to_branch, timestamp, request_id }`
- **merge**: `{ action, author, from_branch, to_branch, timestamp, request_id }`

## Notes
- Only the latest 10 events are shown in the UI and via the API.
- The UI auto-refreshes every 15 seconds.
- MongoDB must be running and accessible.

## License
MIT