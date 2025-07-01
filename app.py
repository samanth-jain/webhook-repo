from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import json
import os
from bson import ObjectId

app = Flask(__name__)

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['github_webhooks']
collection = db['events']

# Custom JSON encoder to handle ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

app.json_encoder = JSONEncoder

@app.route('/')
def index():
    """Serve the main UI page"""
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle GitHub webhook events"""
    try:
        # Get the event type from headers
        event_type = request.headers.get('X-GitHub-Event')
        
        # Support both JSON and x-www-form-urlencoded
        if request.is_json:
            payload = request.get_json()
        elif request.content_type.startswith('application/x-www-form-urlencoded'):
            # GitHub sends the payload as a string under 'payload'
            payload_str = request.form.get('payload')
            if payload_str:
                payload = json.loads(payload_str)
            else:
                payload = None
        else:
            payload = None
        
        if not payload:
            return jsonify({'error': 'No payload received'}), 400
        
        # Process different event types
        event_data = None
        
        if event_type == 'push':
            event_data = process_push_event(payload)
        elif event_type == 'pull_request':
            event_data = process_pull_request_event(payload)
        elif event_type == 'pull_request' and payload.get('action') == 'closed' and payload.get('pull_request', {}).get('merged'):
            event_data = process_merge_event(payload)
        
        if event_data:
            # Store in MongoDB
            result = collection.insert_one(event_data)
            print(f"Stored event: {event_data}")
            return jsonify({'status': 'success', 'id': str(result.inserted_id)}), 200
        
        return jsonify({'status': 'ignored', 'event_type': event_type}), 200
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_push_event(payload):
    """Process push events"""
    try:
        author = payload['head_commit']['author']['name']
        branch = payload['ref'].split('/')[-1]  # Extract branch name from refs/heads/branch_name
        timestamp = datetime.utcnow()
        
        return {
            'action': 'push',
            'author': author,
            'to_branch': branch,
            'from_branch': None,
            'timestamp': timestamp,
            'request_id': payload.get('head_commit', {}).get('id', '')
        }
    except Exception as e:
        print(f"Error processing push event: {e}")
        return None

def process_pull_request_event(payload):
    """Process pull request events"""
    try:
        # Only process 'opened' pull requests
        if payload.get('action') != 'opened':
            return None
            
        author = payload['pull_request']['user']['login']
        from_branch = payload['pull_request']['head']['ref']
        to_branch = payload['pull_request']['base']['ref']
        timestamp = datetime.utcnow()
        
        return {
            'action': 'pull_request',
            'author': author,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'timestamp': timestamp,
            'request_id': str(payload['pull_request']['id'])
        }
    except Exception as e:
        print(f"Error processing pull request event: {e}")
        return None

def process_merge_event(payload):
    """Process merge events (when PR is closed and merged)"""
    try:
        if payload.get('action') != 'closed' or not payload.get('pull_request', {}).get('merged'):
            return None
            
        author = payload['pull_request']['merged_by']['login']
        from_branch = payload['pull_request']['head']['ref']
        to_branch = payload['pull_request']['base']['ref']
        timestamp = datetime.utcnow()
        
        return {
            'action': 'merge',
            'author': author,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'timestamp': timestamp,
            'request_id': str(payload['pull_request']['id'])
        }
    except Exception as e:
        print(f"Error processing merge event: {e}")
        return None

@app.route('/api/events')
def get_events():
    """API endpoint to get latest events"""
    try:
        # Get latest 10 events, sorted by timestamp descending
        events = list(collection.find().sort('timestamp', -1).limit(10))
        
        # Convert ObjectId to string for JSON serialization
        for event in events:
            event['_id'] = str(event['_id'])
            event['timestamp'] = event['timestamp'].isoformat()
        
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    # Create indexes for better performance
    collection.create_index([('timestamp', -1)])
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)