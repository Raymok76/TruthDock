"""
Vote Database Module
Manages voting system for stock and options recommendations
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

# Get the memory database path (same as truthsocial_memory_db.py)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
VOTE_DB = os.path.join(PARENT_DIR, "truthsocial_memory.db")


def init_vote_tables():
    """Initialize vote tables if they don't exist"""
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        
        # Table for storing votes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,  -- 'stock' or 'options'
                vote_value TEXT NOT NULL,  -- 'positive' (看好) or 'negative' (看淡)
                voter_ip TEXT,
                voter_cookie TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        ''')
        
        # Index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_votes_post_type 
            ON votes(post_id, vote_type)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_votes_voter 
            ON votes(voter_ip, voter_cookie)
        ''')
        
        conn.commit()


def has_voted(post_id: int, vote_type: str, voter_ip: Optional[str] = None, voter_cookie: Optional[str] = None) -> bool:
    """
    Check if a voter has already voted on a specific post and vote type
    
    Args:
        post_id: The post ID
        vote_type: 'stock' or 'options'
        voter_ip: Voter's IP address (optional)
        voter_cookie: Voter's cookie ID (optional)
    
    Returns:
        True if voter has already voted
    """
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        
        # Build query: post_id AND vote_type AND (voter_ip OR voter_cookie)
        base_conditions = ['post_id = ?', 'vote_type = ?']
        params = [post_id, vote_type]
        
        voter_conditions = []
        if voter_ip:
            voter_conditions.append('voter_ip = ?')
            params.append(voter_ip)
        if voter_cookie:
            voter_conditions.append('voter_cookie = ?')
            params.append(voter_cookie)
        
        if voter_conditions:
            query = f'''
                SELECT COUNT(*) FROM votes 
                WHERE {' AND '.join(base_conditions)} AND ({' OR '.join(voter_conditions)})
            '''
        else:
            # If no voter identifier provided, can't check
            return False
        
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        return count > 0


def get_vote_value(post_id: int, vote_type: str, voter_ip: Optional[str] = None, voter_cookie: Optional[str] = None) -> Optional[str]:
    """
    Get the vote value for a specific voter on a post and vote type
    
    Args:
        post_id: The post ID
        vote_type: 'stock' or 'options'
        voter_ip: Voter's IP address (optional)
        voter_cookie: Voter's cookie ID (optional)
    
    Returns:
        'positive' or 'negative' if voted, None if not voted
    """
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        
        # Build query: post_id AND vote_type AND (voter_ip OR voter_cookie)
        base_conditions = ['post_id = ?', 'vote_type = ?']
        params = [post_id, vote_type]
        
        voter_conditions = []
        if voter_ip:
            voter_conditions.append('voter_ip = ?')
            params.append(voter_ip)
        if voter_cookie:
            voter_conditions.append('voter_cookie = ?')
            params.append(voter_cookie)
        
        if not voter_conditions:
            # If no voter identifier provided, can't get vote value
            return None
        
        query = f'''
            SELECT vote_value FROM votes 
            WHERE {' AND '.join(base_conditions)} AND ({' OR '.join(voter_conditions)})
            ORDER BY created_at DESC
            LIMIT 1
        '''
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        return result[0] if result else None


def submit_vote(post_id: int, vote_type: str, vote_value: str, 
                voter_ip: Optional[str] = None, voter_cookie: Optional[str] = None) -> bool:
    """
    Submit a vote
    
    Args:
        post_id: The post ID
        vote_type: 'stock' or 'options'
        vote_value: 'positive' (看好) or 'negative' (看淡)
        voter_ip: Voter's IP address (optional)
        voter_cookie: Voter's cookie ID (optional)
    
    Returns:
        True if vote was submitted successfully, False if already voted
    """
    # Check if already voted
    if has_voted(post_id, vote_type, voter_ip, voter_cookie):
        return False
    
    created_at = datetime.now().isoformat()
    
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO votes (post_id, vote_type, vote_value, voter_ip, voter_cookie, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (post_id, vote_type, vote_value, voter_ip, voter_cookie, created_at))
        conn.commit()
        return True


def get_vote_stats(post_id: int) -> Dict[str, Dict[str, int]]:
    """
    Get vote statistics for a post
    
    Returns:
        {
            'stock': {
                'positive': count,
                'negative': count,
                'total': count
            },
            'options': {
                'positive': count,
                'negative': count,
                'total': count
            }
        }
    """
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        
        result = {
            'stock': {'positive': 0, 'negative': 0, 'total': 0},
            'options': {'positive': 0, 'negative': 0, 'total': 0}
        }
        
        for vote_type in ['stock', 'options']:
            cursor.execute('''
                SELECT vote_value, COUNT(*) as count
                FROM votes
                WHERE post_id = ? AND vote_type = ?
                GROUP BY vote_value
            ''', (post_id, vote_type))
            
            rows = cursor.fetchall()
            for vote_value, count in rows:
                if vote_value == 'positive':
                    result[vote_type]['positive'] = count
                elif vote_value == 'negative':
                    result[vote_type]['negative'] = count
            
            result[vote_type]['total'] = result[vote_type]['positive'] + result[vote_type]['negative']
        
        return result


def get_all_post_vote_stats() -> Dict[int, Dict[str, Dict[str, int]]]:
    """
    Get vote statistics for all posts
    
    Returns:
        Dictionary mapping post_id to vote stats
    """
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT post_id FROM votes
        ''')
        post_ids = [row[0] for row in cursor.fetchall()]
        
        result = {}
        for post_id in post_ids:
            result[post_id] = get_vote_stats(post_id)
        
        return result


def bulk_insert_votes(votes: list):
    """
    Bulk insert votes (for fake vote generation)
    
    Args:
        votes: List of tuples (post_id, vote_type, vote_value, voter_ip, voter_cookie, created_at)
    """
    if not votes:
        return
    
    with sqlite3.connect(VOTE_DB) as conn:
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT INTO votes (post_id, vote_type, vote_value, voter_ip, voter_cookie, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', votes)
        conn.commit()


# Initialize tables on import
init_vote_tables()

