from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime, timedelta
import json
import os
from bson import ObjectId
import logging
import pytz
from pytz import timezone 

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

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
        logger.info("Received a webhook request.")
        # Get the event type from headers
        event_type = request.headers.get('X-GitHub-Event')
        logger.info(f"Event type: {event_type}")

        # Support both JSON and x-www-form-urlencoded
        if request.is_json:
            payload = request.get_json()
            logger.info(f"Payload received as JSON: {payload}")
        elif request.content_type.startswith('application/x-www-form-urlencoded'):
            # GitHub sends the payload as a string under 'payload'
            payload_str = request.form.get('payload')
            if payload_str:
                payload = json.loads(payload_str)
                logger.info(f"Payload received as form-urlencoded: {payload}")
            else:
                payload = None
                logger.warning("No payload found in form data.")
        else:
            payload = None
            logger.warning(f"Unsupported content type: {request.content_type}")
        
        if not payload:
            logger.error("No payload received in the request.")
            return jsonify({'error': 'No payload received'}), 400
        
        # Process different event types
        event_data = None
        
        if event_type == 'push':
            logger.info("Processing push event.")
            event_data = process_push_event(payload)
        elif event_type == 'pull_request':
            logger.info("Processing pull_request event.")
            event_data = process_pull_request_event(payload)
        elif event_type == 'pull_request' and payload.get('action') == 'closed' and payload.get('pull_request', {}).get('merged'):
            logger.info("Processing merge event.")
            event_data = process_merge_event(payload)
        else:
            logger.info(f"Event type {event_type} not handled specifically.")
        
        if event_data:
            # Store in MongoDB
            result = collection.insert_one(event_data)
            logger.info(f"Stored event: {event_data}")
            return jsonify({'status': 'success', 'id': str(result.inserted_id)}), 200
        
        logger.info(f"Event ignored: {event_type}")
        return jsonify({'status': 'ignored', 'event_type': event_type}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_push_event(payload):
    """Process push events"""
    try:
        logger.info("Extracting push event details.")
        author = payload['head_commit']['author']['name']
        branch = payload['ref'].split('/')[-1]  # Extract branch name from refs/heads/branch_name
        timestamp = datetime.utcnow()
        logger.info(f"Push event by {author} on branch {branch} at {timestamp}")
        
        return {
            'action': 'push',
            'author': author,
            'to_branch': branch,
            'from_branch': None,
            'timestamp': timestamp,
            'request_id': payload.get('head_commit', {}).get('id', '')
        }
    except Exception as e:
        logger.error(f"Error processing push event: {e}")
        return None

def process_pull_request_event(payload):
    """Process pull request events"""
    try:
        logger.info("Extracting pull request event details.")
        # Only process 'opened' pull requests
        if payload.get('action') != 'opened':
            logger.info(f"Pull request action is not 'opened': {payload.get('action')}")
            return None
            
        author = payload['pull_request']['user']['login']
        from_branch = payload['pull_request']['head']['ref']
        to_branch = payload['pull_request']['base']['ref']
        timestamp = datetime.utcnow()
        logger.info(f"Pull request opened by {author} from {from_branch} to {to_branch} at {timestamp}")
        
        return {
            'action': 'pull_request',
            'author': author,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'timestamp': timestamp,
            'request_id': str(payload['pull_request']['id'])
        }
    except Exception as e:
        logger.error(f"Error processing pull request event: {e}")
        return None

def process_merge_event(payload):
    """Process merge events (when PR is closed and merged)"""
    try:
        logger.info("Extracting merge event details.")
        if payload.get('action') != 'closed' or not payload.get('pull_request', {}).get('merged'):
            logger.info("Merge event ignored: action is not 'closed' or PR not merged.")
            return None
            
        author = payload['pull_request']['merged_by']['login']
        from_branch = payload['pull_request']['head']['ref']
        to_branch = payload['pull_request']['base']['ref']
        timestamp = datetime.utcnow()
        logger.info(f"PR merged by {author} from {from_branch} to {to_branch} at {timestamp}")
        
        return {
            'action': 'merge',
            'author': author,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'timestamp': timestamp,
            'request_id': str(payload['pull_request']['id'])
        }
    except Exception as e:
        logger.error(f"Error processing merge event: {e}")
        return None

@app.route('/api/events')
def get_events():
    """API endpoint to get latest events"""
    try:
        logger.info("Fetching latest events from the database.")
        # Get latest 10 events, sorted by timestamp descending
        fifteen_seconds_ago = datetime.utcnow() - timedelta(seconds=15)
        logger.info(f"Filtering events from: {fifteen_seconds_ago} (UTC)")
        events = list(
            collection.find({'timestamp': {'$gte': fifteen_seconds_ago}})
            .sort('timestamp', -1)
        )
        logger.info(f"Number of events fetched: {len(events)}")
        for event in events:
            event['_id'] = str(event['_id'])
            # Convert UTC to IST for display
            if event.get('timestamp'):
                utc_dt = event['timestamp']
                if utc_dt.tzinfo is None:
                    utc_dt = pytz.utc.localize(utc_dt)
                ist_dt = utc_dt.astimezone(pytz.timezone('Asia/Kolkata'))
                event['timestamp'] = ist_dt.isoformat()
        logger.info("Events processed and ready to return.")
        return jsonify(events)
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
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