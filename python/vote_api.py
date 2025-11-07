#!/usr/bin/env python3
"""
Vote API Server
Flask backend for handling vote submissions and retrievals
"""

import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vote_db import submit_vote, get_vote_stats, has_voted, get_vote_value, init_vote_tables

# Load .env from home directory
home_dir = os.path.expanduser("~")
env_path = os.path.join(home_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for all API routes with explicit origins

# Initialize database tables
init_vote_tables()


def get_voter_id():
    """Get voter identifier from IP or cookie"""
    voter_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if voter_ip:
        voter_ip = voter_ip.split(',')[0].strip()
    
    voter_cookie = request.cookies.get('vote_session_id')
    
    return voter_ip, voter_cookie


@app.route('/api/vote', methods=['POST'])
def vote():
    """Submit a vote"""
    try:
        data = request.get_json()
        
        post_id = data.get('post_id')
        vote_type = data.get('vote_type')  # 'stock' or 'options'
        vote_value = data.get('vote_value')  # 'positive' or 'negative'
        
        if not all([post_id, vote_type, vote_value]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if vote_type not in ['stock', 'options']:
            return jsonify({'error': 'Invalid vote_type'}), 400
        
        if vote_value not in ['positive', 'negative']:
            return jsonify({'error': 'Invalid vote_value'}), 400
        
        # Get voter identifier
        voter_ip, voter_cookie = get_voter_id()
        
        # Check if already voted
        if has_voted(post_id, vote_type, voter_ip, voter_cookie):
            return jsonify({'error': 'Already voted'}), 409
        
        # Submit vote
        success = submit_vote(post_id, vote_type, vote_value, voter_ip, voter_cookie)
        
        if success:
            # Return updated stats
            stats = get_vote_stats(post_id)
            return jsonify({
                'success': True,
                'stats': stats
            }), 200
        else:
            return jsonify({'error': 'Failed to submit vote'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/vote/stats/<int:post_id>', methods=['GET'])
def get_stats(post_id):
    """Get vote statistics for a post"""
    try:
        stats = get_vote_stats(post_id)
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/vote/check/<int:post_id>', methods=['GET'])
def check_vote(post_id):
    """Check if current user has voted"""
    try:
        voter_ip, voter_cookie = get_voter_id()
        
        stock_voted = has_voted(post_id, 'stock', voter_ip, voter_cookie)
        options_voted = has_voted(post_id, 'options', voter_ip, voter_cookie)
        
        stock_vote_value = None
        options_vote_value = None
        
        if stock_voted:
            stock_vote_value = get_vote_value(post_id, 'stock', voter_ip, voter_cookie)
        if options_voted:
            options_vote_value = get_vote_value(post_id, 'options', voter_ip, voter_cookie)
        
        return jsonify({
            'stock_voted': stock_voted,
            'options_voted': options_voted,
            'stock_vote_value': stock_vote_value,
            'options_vote_value': options_vote_value
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    port = int(os.getenv('VOTE_API_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

