#!/usr/bin/env python3
"""
AI Trader Website Generator
Reads Truth Social post analyses from database and generates static HTML website
"""

import sys
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from calendar import monthrange

# Add parent directory to path to import database modules
# Since we're in python/, go up two levels to get to 6_mcp/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import sqlite3

# Get the correct database path - use the same DB path as truthsocial_memory_db.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from truthsocial_memory_db import DB as MEMORY_DB
except ImportError:
    # Fallback to default location
    MEMORY_DB = os.path.join(SCRIPT_DIR, "truthsocial_memory.db")

# Import vote database functions
# We're already in python/, so use SCRIPT_DIR
python_dir = SCRIPT_DIR
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)
from vote_db_json import get_vote_stats  # type: ignore
from sync_votes import sync_votes_from_sqlite_to_json  # type: ignore

# Load environment variables from home directory
env_path = os.path.join(os.path.expanduser("~"), ".env")
load_dotenv(dotenv_path=env_path, override=True)

# Configuration
POSTS_PER_BATCH = 5
INITIAL_VISIBLE_BATCHES = 1  # Show first 5 posts immediately
MAX_POSTS_ON_MAIN_PAGE = 30  # Limit main page to recent 30 posts
OUTPUT_FILE = "index.html"

# Fixed metadata
POSTER_NAME = "Donald J. Trump"
POSTER_ID = "@realDonaldTrump"

# Get Traditional Chinese setting from environment
USE_TRADITIONAL_CHINESE = os.getenv("TRUTHSOCIAL_CHINESE", "false").lower() == "true"


def get_all_analyses(limit: int = MAX_POSTS_ON_MAIN_PAGE) -> List[Dict]:
    """
    Get all post analyses from memory database, newest first
    Returns list of dicts with post info and all AI outputs
    """
    with sqlite3.connect(MEMORY_DB) as conn:
        cursor = conn.cursor()
        
        # Ensure post_content_chinese column exists (for databases created before this feature)
        cursor.execute('''
            PRAGMA table_info(posts)
        ''')
        columns = [col[1] for col in cursor.fetchall()]
        if 'post_content_chinese' not in columns:
            cursor.execute('''
                ALTER TABLE posts ADD COLUMN post_content_chinese TEXT
            ''')
            conn.commit()
        
        # First get the post IDs we want (limited)
        # Order by pinned status first, then by date descending
        cursor.execute('''
            SELECT id FROM posts 
            ORDER BY is_pinned DESC, post_date DESC 
            LIMIT ?
        ''', (limit,))
        post_ids = [row[0] for row in cursor.fetchall()]
        
        if not post_ids:
            return []
        
        # Now get all data for these posts
        placeholders = ','.join('?' * len(post_ids))
        cursor.execute(f'''
            SELECT 
                p.id, p.post_date, p.post_content, COALESCE(p.post_content_chinese, '') as post_content_chinese,
                p.is_pinned,
                ao.ai_type, ao.ai_name, ao.output_content, ao.created_at
            FROM posts p
            LEFT JOIN ai_outputs ao ON p.id = ao.post_id
            WHERE p.id IN ({placeholders})
            ORDER BY p.is_pinned DESC, p.post_date DESC, ao.created_at DESC, ao.ai_type DESC
        ''', post_ids)
        
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        # Group by post - keep only the most recent output for each AI
        posts_dict = {}
        for row in rows:
            post_id, post_date, post_content, post_content_chinese, is_pinned, ai_type, ai_name, output_content, analysis_date = row
            
            if post_id not in posts_dict:
                posts_dict[post_id] = {
                    'id': post_id,
                    'post_date': post_date,
                    'post_content': post_content,
                    'post_content_chinese': post_content_chinese or '',
                    'is_pinned': bool(is_pinned) if is_pinned is not None else False,
                    'openai_output': None,
                    'openai_date': None,
                    'deepseek_output': None,
                    'deepseek_date': None,
                    'evaluator_output': None,
                    'evaluator_date': None,
                    'analysis_date': None
                }
            
            # Assign outputs based on AI name, keeping only the most recent one
            # Since we ORDER BY created_at DESC, the first one we encounter is the newest
            # Note: Grok_Advisor is used in truthsocial1.py (not OpenAI_Advisor)
            if ai_name in ['Grok_Advisor', 'OpenAI_Advisor'] and posts_dict[post_id]['openai_output'] is None:
                posts_dict[post_id]['openai_output'] = output_content
                posts_dict[post_id]['openai_date'] = analysis_date
            elif ai_name == 'DeepSeek_Advisor' and posts_dict[post_id]['deepseek_output'] is None:
                posts_dict[post_id]['deepseek_output'] = output_content
                posts_dict[post_id]['deepseek_date'] = analysis_date
            elif ai_name == 'TradeEvaluator' and posts_dict[post_id]['evaluator_output'] is None:
                posts_dict[post_id]['evaluator_output'] = output_content
                posts_dict[post_id]['evaluator_date'] = analysis_date
                # Use the evaluator's creation time as the analysis date
                if analysis_date:
                    posts_dict[post_id]['analysis_date'] = analysis_date
        
        # Convert to list and sort by pinned status first, then by date descending
        posts_list = list(posts_dict.values())
        # Sort: pinned posts first (is_pinned=True comes first), then by date descending
        # Sort by (is_pinned, date) with reverse=True to get pinned first, then newest dates first
        posts_list.sort(key=lambda x: (x.get('is_pinned', False), x['post_date']), reverse=True)
        
        return posts_list[:limit]


def parse_stock_picks(text: str, is_chinese: bool = False) -> List[Dict]:
    """
    Parse stock picks from AI output text
    Returns list of dicts with ticker, action, reasoning, confidence
    Extracts specifically from "Top 1", "Top 2", "Top 3" format
    """
    if not text:
        return []
    
    stocks = []
    
    # Look for STOCK PICKS section
    patterns = [
        r'\*\*STOCK PICKS[^:]*:\*\*(.+?)(?:\*\*OPTIONS PICKS|\*\*期權建議|$)',
        r'\*\*股票建議[^:：]*[:：]\*\*(.+?)(?:\*\*OPTIONS|\*\*期權|$)',
    ]
    
    stock_section = None
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            stock_section = match.group(1)
            break
    
    if not stock_section:
        return []

    # Extract "Top 1", "Top 2", "Top 3" picks
    # Pattern: **Top 1: TICKER (optional name)** - BUY/SELL/HOLD/PASS
    # Also handle Chinese: **Top 1: TICKER** - 買入/賣出/持有
    # Note: Format can be **Top 1: XOM - BUY** or **Top 1: XOM** - BUY
    top_patterns = [
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})(?:\s*\([^)]+\))?\*\*\s*[-–]\s*(BUY|SELL|HOLD|PASS|買入|賣出|持有)',
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})(?:\s*\([^)]+\))?\*\*\s*[-–]?\s*(BUY|SELL|HOLD|PASS|買入|賣出|持有)',
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\s*[-–]\s*(BUY|SELL|HOLD|PASS|買入|賣出|持有)\*\*',
        r'(?:^|\n)(\d+)\.\s*\*\*([A-Z]{2,5})(?:\s*\([^)]+\))?\*\*\s*[-–]\s*(BUY|SELL|HOLD|PASS|買入|賣出|持有)',
        # Handle Chinese format: **Top 1: TICKER** - 買入 (without **)
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\*\*\s*[-–]\s*(買入|賣出|持有)',
    ]
    
    for pattern in top_patterns:
        matches = re.finditer(pattern, stock_section, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            top_num = int(match.group(1))
            ticker = match.group(2)
            action = match.group(3).upper()
            
            # Skip false positives and PASS recommendations
            if ticker in ['BUY', 'SELL', 'CALL', 'PUT', 'ETF', 'PASS', 'TOP'] or action == 'PASS':
                continue

            # Translate Traditional Chinese actions
            if action == '買入':
                action = 'BUY'
            elif action == '賣出':
                action = 'SELL'
            elif action == '持有':
                action = 'HOLD'

            # Check if already added
            if not any(s['ticker'] == ticker for s in stocks):
                stocks.append({
                    'ticker': ticker,
                    'action': action,
                    'top_num': top_num,
                    'reasoning': '',
                    'confidence': 'Medium'
                })
    
    # Sort by top number and return max 3
    stocks.sort(key=lambda x: x.get('top_num', 999))
    return stocks[:3]


def convert_chinese_date_to_english(date_str: str) -> str:
    """
    Convert Chinese date format to English format
    Examples:
        "2026年1月底到期" -> "Jan 31, 2026"
        "2026年2月到期" -> "Feb 2026"
        "2026年1月31日到期" -> "Jan 31, 2026"
    """
    if not date_str:
        return date_str
    
    # Remove "到期" suffix
    date_str = date_str.replace('到期', '').strip()
    
    # Pattern: YYYY年MM月底 -> "MMM DD, YYYY" (assuming last day of month)
    match = re.search(r'(\d{4})年(\d{1,2})月底', date_str)
    if match:
        year = match.group(1)
        month = int(match.group(2))
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if 1 <= month <= 12:
            # Get last day of month
            last_day = monthrange(int(year), month)[1]
            return f"{month_names[month-1]} {last_day}, {year}"
    
    # Pattern: YYYY年MM月 -> "MMM YYYY"
    match = re.search(r'(\d{4})年(\d{1,2})月(?!底)', date_str)
    if match:
        year = match.group(1)
        month = int(match.group(2))
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if 1 <= month <= 12:
            return f"{month_names[month-1]} {year}"
    
    # Pattern: YYYY年MM月DD日 -> "MMM DD, YYYY"
    match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if match:
        year = match.group(1)
        month = int(match.group(2))
        day = match.group(3)
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if 1 <= month <= 12:
            return f"{month_names[month-1]} {day}, {year}"
    
    # If no pattern matched, return original
    return date_str


def parse_options_picks(text: str, is_chinese: bool = False) -> List[Dict]:
    """
    Parse options picks from AI output text
    Returns list of dicts with ticker, type, strike, expiry, confidence
    Extracts specifically from "Top 1", "Top 2", "Top 3" format
    """
    if not text:
        return []
    
    options = []
    
    # Look for OPTIONS PICKS section
    patterns = [
        r'\*\*OPTIONS PICKS[^:]*:\*\*(.+?)(?:\*\*FINAL VERDICT|\*\*總結|---|$)',
        r'\*\*期權建議[^:：]*[:：]\*\*(.+?)(?:\*\*FINAL|\*\*總結|---|$)',
    ]
    
    options_section = None
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            options_section = match.group(1)
            break
    
    if not options_section:
        return []

    # Extract "Top 1", "Top 2", "Top 3" picks
    # Pattern: **Top 1: TICKER CALL/PUT** at $strike exp date
    # Also handle: **Top 1: XOM CALL at $120 exp 2026-01-31** (closing ** after expiry)
    # Also handle Chinese: **Top 1: TICKER CALL/PUT** 行使價 $strike 2026年1月底到期
    # Remove Chinese words like 期權, 行使價 and convert Chinese dates to English format
    top_patterns = [
        # Format: **Top 1: XOM CALL at $120 exp 2026-01-31** (closing ** after expiry)
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\s+(CALL|PUT|PASS|認購|認沽)\s+at\s*[$](\d+)\s*exp\s*([^<\n*]+?)\*\*',
        # Format: **Top 1: TICKER CALL** at $strike exp date (closing ** before at)
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\s+(CALL|PUT|PASS|認購|認沽)\*\*\s*at\s*[$](\d+)(?:\s*exp\s*([^<\n]+))?',
        r'(?:^|\n)(\d+)\.\s*\*\*([A-Z]{2,5})\s+(CALL|PUT|PASS|認購|認沽)\*\*\s*(?:at\s*[$](\d+)(?:\s*exp\s*([^<\n]+))?)?',
        # Chinese format: **Top 1: TICKER CALL** 行使價 $strike 2026年1月底到期
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\s+(CALL|PUT|認購|認沽)\*\*\s*(?:行使價\s*)?[$]?(\d+)?\s*(?:exp\s*)?([^<\n]+)?',
        # Chinese format without strike: **Top 1: TICKER CALL** 2026年1月底到期
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\s+(CALL|PUT|認購|認沽)\*\*\s*(?:，|\s)+([^<\n]+?)(?:到期|$)',
    ]
    
    for pattern in top_patterns:
        matches = re.finditer(pattern, options_section, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            groups = match.groups()
            top_num = int(groups[0])
            ticker = groups[1]
            option_type = groups[2].upper()
            
            # Handle different patterns with different group structures
            # Pattern 1: **Top 1: XOM CALL at $120 exp 2026-01-31** (5 groups: num, ticker, type, strike, expiry)
            if len(groups) >= 5 and groups[4] and groups[4].strip():
                # Pattern with strike and expiry: groups[3]=strike, groups[4]=expiry
                strike = groups[3] if groups[3] else '?'
                expiry = groups[4].strip() if groups[4] else ''
            elif len(groups) >= 4:
                # Pattern with only expiry or strike: groups[3] could be either
                # Check if it looks like a date (contains Chinese chars or date pattern)
                if groups[3] and (re.search(r'[\u4e00-\u9fff]', groups[3]) or re.search(r'\d{4}', groups[3])):
                    expiry = groups[3].strip()
                    strike = '?'
                else:
                    strike = groups[3] if groups[3] else '?'
                    expiry = ''
            else:
                strike = '?'
                expiry = ''
            
            # Skip false positives and PASS recommendations
            if ticker in ['CALL', 'PUT', 'ETF', 'PASS', 'TOP'] or option_type == 'PASS':
                continue
            
            # Translate Traditional Chinese
            if option_type == '認購':
                option_type = 'CALL'
            elif option_type == '認沽':
                option_type = 'PUT'
            
            # Clean up expiry date - remove Chinese words and convert dates
            if expiry:
                # Remove Chinese words like 期權, 行使價, 到期
                expiry = re.sub(r'[期權行使價到期]', '', expiry).strip()
                # Convert Chinese date format to English if needed
                if re.search(r'[\u4e00-\u9fff]', expiry):
                    expiry = convert_chinese_date_to_english(expiry)
                # Clean up any remaining Chinese characters
                expiry = re.sub(r'[\u4e00-\u9fff]', '', expiry).strip()
            
            # Check if already added
            if not any(o['ticker'] == ticker and o['type'] == option_type for o in options):
                options.append({
                    'ticker': ticker,
                    'type': option_type,
                    'strike': strike,
                    'top_num': top_num,
                    'expiry': expiry,
                    'confidence': 'Medium'
                })
    
    # Sort by top number and return max 3
    options.sort(key=lambda x: x.get('top_num', 999))
    return options[:3]


def format_datetime(iso_datetime: str) -> str:
    """Format ISO datetime to readable format"""
    try:
        dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_datetime


def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not text:
        return ""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def detect_language(text: str) -> str:
    """Detect if text is primarily Traditional Chinese"""
    if not text:
        return 'en'
    # Simple heuristic: if more than 30% Chinese characters, consider it Chinese
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.replace(' ', ''))
    return 'zh' if (total_chars > 0 and chinese_chars / total_chars > 0.3) else 'en'


def simple_markdown_to_html(text: str) -> str:
    """
    Convert simple markdown to HTML
    Handles: **bold**, bullet lists, line breaks, BUY/SELL/HOLD badges, exp dates
    """
    if not text:
        return ""
    
    # Convert **bold** to <strong>
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    
    # Convert bullet points (- item) to list items
    lines = text.split('\n')
    html_lines = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        # Check if line is a bullet point
        if re.match(r'^[-*]\s+', stripped):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            item_text = re.sub(r'^[-*]\s+', '', stripped)
            html_lines.append(f'<li>{item_text}</li>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if stripped:
                # Style BUY/SELL/HOLD in stock picks (pattern: " - BUY" or " - SELL" or " - HOLD")
                stripped = re.sub(
                    r'\s*[-–]\s*(BUY)\b', 
                    r' <span class="action-badge action-buy">BUY</span>', 
                    stripped, 
                    flags=re.IGNORECASE
                )
                stripped = re.sub(
                    r'\s*[-–]\s*(SELL)\b', 
                    r' <span class="action-badge action-sell">SELL</span>', 
                    stripped, 
                    flags=re.IGNORECASE
                )
                stripped = re.sub(
                    r'\s*[-–]\s*(HOLD)\b', 
                    r' <span class="action-badge action-hold">HOLD</span>', 
                    stripped, 
                    flags=re.IGNORECASE
                )
                
                # Remove "at " before dollar amounts in options picks
                stripped = re.sub(
                    r'\bat\s+(\$[0-9,]+)',
                    r'\1',
                    stripped,
                    flags=re.IGNORECASE
                )
                
                # Style dollar amounts as strike badges ONLY for option strike prices
                # Only apply to dollar amounts that are:
                # 1. Preceded by CALL/PUT - these are strike prices in option recommendations
                # 2. Immediately followed by "exp" (expiry) - these are strike prices  
                # DO NOT apply to regular paragraph text about stock prices
                
                # First, handle strike prices after CALL/PUT in recommendation lines
                # Pattern: "Top X: TICKER CALL $95" or "TICKER CALL $95" or "CALL $95 exp"
                # Must come BEFORE general "$X exp" pattern to avoid double-processing
                stripped = re.sub(
                    r'\b(CALL|PUT)\s+\$([0-9,]+)',
                    r'\1 <span class="strike-badge">$\2</span>',
                    stripped,
                    flags=re.IGNORECASE
                )
                
                # Then handle standalone strike prices followed by expiry (for cases without CALL/PUT)
                # Pattern: "$95 exp 2026-01-31"
                # This won't double-match because CALL/PUT patterns are already processed above
                stripped = re.sub(
                    r'\$([0-9,]+)\s+exp\b',
                    r'<span class="strike-badge">$\1</span> exp',
                    stripped,
                    flags=re.IGNORECASE
                )
                
                # Style expiry dates in options picks (pattern: "exp 2026-02-28" or "exp Feb 2026")
                stripped = re.sub(
                    r'\bexp\s+([0-9]{4}-[0-9]{2}-[0-9]{2}|[A-Za-z]+-?[A-Za-z]*\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{4}/[0-9]{2}/[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4})',
                    r'<span class="expiry-badge">exp \1</span>',
                    stripped,
                    flags=re.IGNORECASE
                )
                
                # Style CALL/PUT mentions
                stripped = re.sub(
                    r'\b(CALL)\b',
                    r' <span class="action-badge action-call">CALL</span>',
                    stripped,
                    flags=re.IGNORECASE
                )
                stripped = re.sub(
                    r'\b(PUT)\b',
                    r' <span class="action-badge action-put">PUT</span>',
                    stripped,
                    flags=re.IGNORECASE
                )
                
                html_lines.append(f'<p>{stripped}</p>')
            elif html_lines:  # Empty line, add spacing
                html_lines.append('<br>')
    
    # Close list if still open
    if in_list:
        html_lines.append('</ul>')
    
    return '\n'.join(html_lines)


def split_ai_output_into_sections(text: str) -> Dict[str, str]:
    """
    Split AI evaluator output into three sections:
    1. STOCK PICKS
    2. OPTIONS PICKS  
    3. FINAL VERDICT
    
    Removes unwanted sections like AGENT COMPARISON, separators, etc.
    """
    if not text:
        return {
            'stock_picks': 'No stock recommendations available.',
            'options_picks': 'No options recommendations available.',
            'final_verdict': 'No final verdict available.'
        }
    
    # Extract STOCK PICKS section
    stock_section = ''
    stock_patterns = [
        r'\*\*STOCK PICKS[^:]*:\*\*(.+?)(?:\*\*OPTIONS PICKS|\*\*期權建議|$)',
        r'\*\*股票建議[^:：]*[:：]\*\*(.+?)(?:\*\*OPTIONS|\*\*期權|$)',
    ]
    for pattern in stock_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            stock_section = match.group(1).strip()
            break
    
    # Extract OPTIONS PICKS section
    options_section = ''
    options_patterns = [
        r'\*\*OPTIONS PICKS[^:]*:\*\*(.+?)(?:\*\*FINAL VERDICT|\*\*總結|---|$)',
        r'\*\*期權建議[^:：]*[:：]\*\*(.+?)(?:\*\*FINAL|\*\*總結|---|$)',
    ]
    for pattern in options_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            options_section = match.group(1).strip()
            break
    
    # Extract FINAL VERDICT section
    verdict_section = ''
    verdict_patterns = [
        r'\*\*FINAL VERDICT[^:]*:\*\*(.+?)$',
        r'\*\*總結[^:：]*[:：]\*\*(.+?)$',
    ]
    for pattern in verdict_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            verdict_section = match.group(1).strip()
            break
    
    # Clean up sections - remove separators and unwanted content
    def clean_section(section_text):
        # Remove --- separators
        section_text = re.sub(r'^[-–—]{3,}$', '', section_text, flags=re.MULTILINE)
        # Remove empty lines at start/end
        section_text = section_text.strip()
        # Remove AGENT COMPARISON section if it somehow got included
        section_text = re.sub(r'\*\*AGENT COMPARISON:\*\*.+?(?=\*\*|$)', '', section_text, flags=re.DOTALL | re.IGNORECASE)
        # Remove FINAL UNIFIED RECOMMENDATIONS title
        section_text = re.sub(r'\*\*FINAL UNIFIED RECOMMENDATIONS:\*\*', '', section_text, flags=re.IGNORECASE)
        # Remove Traditional Chinese meta sentences (multiple patterns to catch all variations)
        # Remove old Cantonese meta sentences (粵語)
        section_text = re.sub(r'[（(]?以上.*?粵語.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'[（(]?全文.*?粵語.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'[（(]?.*?以.*?粵語.*?撰寫.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        # Remove Traditional Chinese meta sentences (繁體中文)
        section_text = re.sub(r'[（(]?以上.*?繁體中文.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'[（(]?全文.*?繁體中文.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'[（(]?.*?以.*?繁體中文.*?撰寫.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        # Remove generic language requirement meta sentences
        section_text = re.sub(r'[（(]?.*?符合要求.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'[（(]?.*?符合語言要求.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        # Remove personality mentions (中環人)
        section_text = re.sub(r'[（(]?.*?中環人.*?[）)]?\.?', '', section_text, flags=re.MULTILINE | re.IGNORECASE)
        section_text = re.sub(r'[（(]?.*?Central Hong Kong.*?[）)]?\.?', '', section_text, flags=re.MULTILINE | re.IGNORECASE)
        # Remove # tags (hashtags)
        section_text = re.sub(r'#\w+', '', section_text)
        section_text = re.sub(r'#\s+', '', section_text)
        # Remove standalone # characters
        section_text = re.sub(r'\s+#\s+', ' ', section_text)
        section_text = re.sub(r'^\s*#\s*', '', section_text, flags=re.MULTILINE)
        # Remove specific PASS sentence about no additional opportunities beyond core sectors
        # Pattern matches: "PASS - No strong additional stock or option opportunities identified beyond core energy, security, and defense sectors due to limited直接市場影響 from政治醜聞消息。"
        # Match the exact pattern with mixed English and Chinese
        section_text = re.sub(
            r'PASS\s*[-–—]?\s*No\s+strong\s+additional\s+stock\s+or\s+option\s+opportunities\s+identified\s+beyond\s+core\s+energy[^。]*直接市場影響[^。]*政治醜聞消息[^。]*[。]?',
            '',
            section_text,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        # Match Chinese variations
        section_text = re.sub(
            r'PASS\s*[-–—]?\s*無其他強烈.*?直接市場影響.*?政治醜聞消息[^。]*[。]?',
            '',
            section_text,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        # More flexible pattern to catch any variation with "PASS", "direct market impact", and "political scandal"
        section_text = re.sub(
            r'PASS\s*[-–—]?\s*No\s+strong\s+additional.*?直接市場影響.*?政治醜聞消息[^。]*[。]?',
            '',
            section_text,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        return section_text.strip()
    
    return {
        'stock_picks': clean_section(stock_section) or 'No stock recommendations available.',
        'options_picks': clean_section(options_section) or 'No options recommendations available.',
        'final_verdict': clean_section(verdict_section) or 'No final verdict available.'
    }


def generate_vote_html(post_id: int) -> str:
    """
    Generate HTML for vote section
    
    Args:
        post_id: Post ID from memory database
    
    Returns:
        HTML string for vote section
    """
    # Get vote statistics
    stats = get_vote_stats(post_id)
    
    stock_stats = stats.get('stock', {'positive': 0, 'negative': 0, 'total': 0})
    options_stats = stats.get('options', {'positive': 0, 'negative': 0, 'total': 0})
    
    # Calculate percentages
    stock_total = stock_stats['total']
    stock_positive_pct = (stock_stats['positive'] / stock_total * 100) if stock_total > 0 else 0
    stock_negative_pct = (stock_stats['negative'] / stock_total * 100) if stock_total > 0 else 0
    
    options_total = options_stats['total']
    options_positive_pct = (options_stats['positive'] / options_total * 100) if options_total > 0 else 0
    options_negative_pct = (options_stats['negative'] / options_total * 100) if options_total > 0 else 0
    
    vote_html = f'''
            <div class="vote-section" data-post-id="{post_id}">
                <!-- Stock Vote -->
                <div class="vote-item">
                    <div class="vote-question">
                        你怎麼看這次的<span class="vote-keyword-stock">股票</span>推薦?
                    </div>
                    <div class="vote-options">
                        <button class="vote-button vote-positive" data-post-id="{post_id}" data-vote-type="stock" data-vote-value="positive" onclick="handleVote(this)">
                            <span class="vote-option-text">看好</span>
                            <span class="vote-count vote-stats-hidden" id="stock-positive-count-{post_id}">{stock_stats['positive']}票</span>
                            <span class="vote-percentage vote-stats-hidden" id="stock-positive-pct-{post_id}">{stock_positive_pct:.1f}%</span>
                        </button>
                        <button class="vote-button vote-negative" data-post-id="{post_id}" data-vote-type="stock" data-vote-value="negative" onclick="handleVote(this)">
                            <span class="vote-option-text">看淡</span>
                            <span class="vote-count vote-stats-hidden" id="stock-negative-count-{post_id}">{stock_stats['negative']}票</span>
                            <span class="vote-percentage vote-stats-hidden" id="stock-negative-pct-{post_id}">{stock_negative_pct:.1f}%</span>
                        </button>
                    </div>
                </div>
                
                <!-- Options Vote -->
                <div class="vote-item">
                    <div class="vote-question">
                        你怎麼看這次的<span class="vote-keyword-options">期權</span>推薦?
                    </div>
                    <div class="vote-options">
                        <button class="vote-button vote-positive" data-post-id="{post_id}" data-vote-type="options" data-vote-value="positive" onclick="handleVote(this)">
                            <span class="vote-option-text">看好</span>
                            <span class="vote-count vote-stats-hidden" id="options-positive-count-{post_id}">{options_stats['positive']}票</span>
                            <span class="vote-percentage vote-stats-hidden" id="options-positive-pct-{post_id}">{options_positive_pct:.1f}%</span>
                        </button>
                        <button class="vote-button vote-negative" data-post-id="{post_id}" data-vote-type="options" data-vote-value="negative" onclick="handleVote(this)">
                            <span class="vote-option-text">看淡</span>
                            <span class="vote-count vote-stats-hidden" id="options-negative-count-{post_id}">{options_stats['negative']}票</span>
                            <span class="vote-percentage vote-stats-hidden" id="options-negative-pct-{post_id}">{options_negative_pct:.1f}%</span>
                        </button>
                    </div>
                </div>
            </div>
    '''
    
    return vote_html


def generate_post_card_html(post: Dict, batch_num: int, is_visible: bool = False) -> str:
    """Generate HTML for a single post card"""
    
    # Detect language from evaluator output (final recommendation)
    evaluator_text = post.get('evaluator_output', '') or ''
    is_chinese = detect_language(evaluator_text)
    
    # Get post ID for vote stats
    post_id = post.get('id')
    
    # Parse stock and options picks from evaluator output
    stocks = parse_stock_picks(evaluator_text, is_chinese)
    options = parse_options_picks(evaluator_text, is_chinese)
    
    # Format datetime
    formatted_date = format_datetime(post['post_date'])
    
    # Format analysis date
    analysis_date = post.get('analysis_date')
    if analysis_date:
        formatted_analysis_date = format_datetime(analysis_date)
        analysis_date_label = "分析日期" if is_chinese == 'zh' else "Analysis Date"
        current_date_label = "現在日期" if is_chinese == 'zh' else "Current Date"
        analysis_date_html = f'''<div class="date-container">
            <div class="time-ago-tag" data-analysis-date="{analysis_date}"></div>
            <div class="dates-right">
                <div class="analysis-date">{analysis_date_label}: {formatted_analysis_date}</div>
                <div class="current-date">{current_date_label}: <span class="current-date-time"></span></div>
            </div>
        </div>'''
    else:
        analysis_date_html = ''
    
    # Get first stock and option for header display
    primary_stock = stocks[0] if stocks else None
    primary_option = options[0] if options else None
    
    # Determine visibility class
    visibility_class = '' if is_visible else 'hidden-post'
    
    # Stock/Options summary cards HTML
    stock_card_html = ''
    if primary_stock:
        action = primary_stock['action']
        if action == 'BUY':
            action_text = '買入 (BUY)' if is_chinese == 'zh' else 'BUY'
            action_class = 'card-action-buy'
        elif action == 'SELL':
            action_text = '賣出 (SELL)' if is_chinese == 'zh' else 'SELL'
            action_class = 'card-action-sell'
        elif action == 'HOLD':
            action_text = '持有 (HOLD)' if is_chinese == 'zh' else 'HOLD'
            action_class = 'card-action-hold'
        else:  # Default to BUY for unknown actions
            action_text = '買入 (BUY)' if is_chinese == 'zh' else 'BUY'
            action_class = 'card-action-buy'
        
        stock_card_html = f'''
        <div class="summary-card">
            <div class="card-ticker">{primary_stock['ticker']}</div>
            <div class="card-action {action_class}">{action_text}</div>
        </div>
        '''
    else:
        nil_text = '無' if is_chinese == 'zh' else 'NIL'
        stock_card_html = f'''
        <div class="summary-card empty">
            <div class="card-empty">{nil_text}</div>
        </div>
        '''
    
    option_card_html = ''
    if primary_option:
        # Determine language for labels
        best_buy_label = '最佳時機' if is_chinese == 'zh' else 'Best Buy'
        target_label = '目標' if is_chinese == 'zh' else 'Target'
        
        # Determine action class based on type
        option_type = primary_option['type']
        action_class = 'card-action-call' if option_type == 'CALL' else 'card-action-put'
        
        # Create timeline gauge if we have strike and expiry
        gauge_html = ''
        if primary_option['strike'] != '?' and primary_option.get('expiry'):
            expiry_text = primary_option.get('expiry', '').strip()
            gauge_html = f'''
            <div class="option-timeline" data-post-date="{post['post_date']}" data-expiry="{expiry_text}">
                <div class="timeline-bar">
                    <div class="timeline-indicator">
                        <div class="timeline-label timeline-current">{best_buy_label}</div>
                    </div>
                </div>
                <div class="timeline-labels">
                    <div class="timeline-label timeline-target">{target_label}: ${primary_option["strike"]}</div>
                    <div class="timeline-label timeline-expiry">{expiry_text}</div>
                </div>
            </div>
            '''
        
        option_card_html = f'''
        <div class="summary-card">
            <div class="card-ticker">{primary_option['ticker']}</div>
            <div class="card-action {action_class}">{option_type}</div>
            {gauge_html}
        </div>
        '''
    else:
        nil_text = '無' if is_chinese == 'zh' else 'NIL'
        option_card_html = f'''
        <div class="summary-card empty">
            <div class="card-empty">{nil_text}</div>
        </div>
        '''
    
    # Split AI output into 3 sections
    sections = split_ai_output_into_sections(evaluator_text)
    
    # Convert markdown to HTML for each section
    stock_picks_html = simple_markdown_to_html(sections['stock_picks'])
    options_picks_html = simple_markdown_to_html(sections['options_picks'])
    final_verdict_html = simple_markdown_to_html(sections['final_verdict'])
    
    # Use full post content (no truncation)
    post_content = post['post_content']
    post_content_chinese = post.get('post_content_chinese', '')
    
    # Generate language tabs HTML
    if post_content_chinese:
        lang_tabs_html = f'''
                <div class="post-language-tabs">
                    <button class="lang-tab active" data-lang="eng" onclick="switchLanguage(this, 'eng')">Eng</button>
                    <button class="lang-tab" data-lang="zh" onclick="switchLanguage(this, 'zh')">中</button>
                </div>
                <div class="post-content post-content-eng">
                    {escape_html(post_content)}
                </div>
                <div class="post-content post-content-zh" style="display: none;">
                    {escape_html(post_content_chinese)}
                </div>
        '''
    else:
        lang_tabs_html = f'''
                <div class="post-content">
                    {escape_html(post_content)}
                </div>
        '''
    
    # Determine section headers based on language setting
    stock_picks_header = "📈 股票建議" if USE_TRADITIONAL_CHINESE else "📈 Stock Picks"
    options_picks_header = "📊 期權建議" if USE_TRADITIONAL_CHINESE else "📊 Options Picks"
    final_verdict_header = "🎯 總結" if USE_TRADITIONAL_CHINESE else "🎯 Final Verdict"
    
    html = f'''
    <article class="post-card {visibility_class}" data-batch="{batch_num}">
        {analysis_date_html}
        <div class="header-vote-wrapper">
            <div class="post-header">
                <div class="header-left">
                    <h2 class="section-title">Stock 股票</h2>
                    {stock_card_html}
                </div>
                
                <div class="header-center">
                    <h2 class="section-title">Options 期權</h2>
                    {option_card_html}
                </div>
            </div>
            
            <div class="meta-content-cell">
                <div class="truth-logo">
                    <img src="assets/truth_logo.png" alt="Truth Social" onerror="this.style.display='none'">
                </div>
                
                <div class="post-meta">
                    <img src="assets/trump_icon.jpg" alt="Trump" class="poster-icon" onerror="this.style.display='none'">
                    <div class="meta-text">
                        <div class="meta-date">
                            {'📌 ' if post.get('is_pinned', False) else ''}Post Date: {formatted_date}
                        </div>
                        <div class="meta-name">{POSTER_NAME}</div>
                        <div class="meta-id">{POSTER_ID}</div>
                    </div>
                </div>
                
                {lang_tabs_html}
            </div>
            
            <div class="vote-cell">
                {generate_vote_html(post_id) if post_id else '<!-- No vote data -->'}
            </div>
        </div>
        
        <div class="post-body">
            <div class="analysis-section section-gray-1">
                <h3>{stock_picks_header}</h3>
                <div class="analysis-content">
                    {stock_picks_html}
                </div>
            </div>
            
            <div class="analysis-section section-gray-2">
                <h3>{options_picks_header}</h3>
                <div class="analysis-content">
                    {options_picks_html}
                </div>
            </div>
            
            <div class="analysis-section section-gray-1">
                <h3>{final_verdict_header}</h3>
                <div class="analysis-content">
                    {final_verdict_html}
                </div>
            </div>
        </div>
    </article>
    '''
    
    return html


def generate_html_page(posts: List[Dict]) -> str:
    """Generate complete HTML page with all posts"""
    
    if not posts:
        posts_html = '<div class="no-posts">No analyses available yet. Run truthsocial1.py to generate analyses.</div>'
        total_batches = 0
    else:
        # Generate post cards
        posts_html_parts = []
        for i, post in enumerate(posts):
            batch_num = (i // POSTS_PER_BATCH) + 1
            is_visible = batch_num <= INITIAL_VISIBLE_BATCHES
            posts_html_parts.append(generate_post_card_html(post, batch_num, is_visible))
        
        posts_html = '\n'.join(posts_html_parts)
        total_batches = ((len(posts) - 1) // POSTS_PER_BATCH) + 1
    
    # Get current timestamp
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AlphaFrog -- Financial News and Analysis</title>
    <link rel="stylesheet" href="styles.css">
    <style>
        /* Hide vote stats initially */
        .vote-stats-hidden {{
            display: none !important;
        }}
    </style>
</head>
<body>
    <header class="main-header">
        <img src="assets/mainlogo02.png" alt="Alpha Frog Logo" class="header-logo">
    </header>
    
    <main id="posts-container">
        {posts_html}
    </main>
    
    <div id="loading-indicator" class="loading hidden">
        <div class="spinner"></div>
        <p>Loading more analyses...</p>
    </div>
    
    <div id="end-message" class="end-message hidden">
        <p>✓ All posts loaded</p>
    </div>
    
    <footer class="main-footer">
        <div class="footer-disclaimer">
            <div class="disclaimer-section">
                <h3 class="disclaimer-title">⚠️ Risk Warning</h3>
                <p class="disclaimer-text">
                    <strong>Risk Warning:</strong> All stock suggestions and recommendations on this website carry inherent investment risks. Please carefully assess your risk tolerance and do not invest funds you cannot afford to lose. Consult a qualified financial advisor before making investment decisions. Past performance does not guarantee future results.
                </p>
            </div>
            <div class="disclaimer-section">
                <h3 class="disclaimer-title">⚠️ 風險警告</h3>
                <p class="disclaimer-text">
                    <strong>風險警告：</strong> 本網站提供的所有股票建議及推薦均存在固有投資風險。請仔細評估您的風險承受能力，切勿投資您無法承受損失的資金。在作出投資決定前，請諮詢合資格的財務顧問。過往表現並不保證未來結果。
                </p>
            </div>
        </div>
        <div class="footer-copyright">
            <p>Powered by AlphaFrog, all rights reserved.</p>
        </div>
    </footer>
    
    <script>
        const TOTAL_BATCHES = {total_batches};
        const INITIAL_VISIBLE = {INITIAL_VISIBLE_BATCHES};
        
        // Update current datetime
        function updateCurrentDateTime() {{
            const elements = document.querySelectorAll('.current-date-time');
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            const formatted = `${{year}}-${{month}}-${{day}} ${{hours}}:${{minutes}}:${{seconds}}`;
            
            elements.forEach(el => {{
                el.textContent = formatted;
            }});
        }}
        
        // Convert number to Arabic numerals (replacing Chinese characters)
        function numberToChinese(num, isCompound = false) {{
            // Simply return Arabic numerals instead of Chinese characters
            return num.toString();
        }}
        
        // Calculate and update time ago tags
        function updateTimeAgoTags() {{
            const tags = document.querySelectorAll('.time-ago-tag');
            const now = new Date();
            
            tags.forEach(tag => {{
                const analysisDateStr = tag.getAttribute('data-analysis-date');
                if (!analysisDateStr) return;
                
                // Parse ISO datetime (handle both Z and +00:00 formats)
                const analysisDate = new Date(analysisDateStr.replace('Z', '+00:00'));
                const diffMs = now - analysisDate;
                
                // Less than 1 minute: no tag
                if (diffMs < 60000) {{
                    tag.textContent = '';
                    tag.style.display = 'none';
                    return;
                }}
                
                // Less than 1 hour: show minutes
                if (diffMs < 3600000) {{
                    const minutes = Math.floor(diffMs / 60000);
                    const minutesText = numberToChinese(minutes);
                    tag.textContent = `${{minutesText}}分鐘前`;
                    tag.style.display = 'inline';
                    return;
                }}
                
                // Less than 1 day: show hours
                if (diffMs < 86400000) {{
                    const hours = Math.floor(diffMs / 3600000);
                    const hoursText = numberToChinese(hours);
                    tag.textContent = `${{hoursText}}小時前`;
                    tag.style.display = 'inline';
                    return;
                }}
                
                // 1 day or more: show days
                const days = Math.floor(diffMs / 86400000);
                const daysText = numberToChinese(days);
                tag.textContent = `${{daysText}}日前`;
                tag.style.display = 'inline';
            }});
        }}
        
        // Combined update function
        function updateDateTimeAndTimeAgo() {{
            updateCurrentDateTime();
            updateTimeAgoTags();
        }}
        
        // Update on page load
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', updateDateTimeAndTimeAgo);
        }} else {{
            updateDateTimeAndTimeAgo();
        }}
        
        // Update every second for real-time clock and time ago tags
        setInterval(updateDateTimeAndTimeAgo, 1000);
        
        // Language tab switching function
        function switchLanguage(button, lang) {{
            const tabs = button.parentElement;
            const metaContentCell = tabs.closest('.meta-content-cell');
            
            // Update active tab
            tabs.querySelectorAll('.lang-tab').forEach(tab => {{
                tab.classList.remove('active');
            }});
            button.classList.add('active');
            
            // Show/hide content
            const engContent = metaContentCell.querySelector('.post-content-eng');
            const zhContent = metaContentCell.querySelector('.post-content-zh');
            
            if (lang === 'eng') {{
                if (engContent) {{
                    engContent.style.display = 'block';
                }}
                if (zhContent) {{
                    zhContent.style.display = 'none';
                }}
            }} else if (lang === 'zh') {{
                if (engContent) {{
                    engContent.style.display = 'none';
                }}
                if (zhContent) {{
                    zhContent.style.display = 'block';
                }}
            }}
        }}
        
        // Post navigation functionality
        function initPostNavigation() {{
            const posts = Array.from(document.querySelectorAll('.post-card:not(.hidden-post)'));
            const totalPosts = posts.length;
            
            if (totalPosts <= 1) {{
                // Hide navigation if only one or no posts
                const navButtons = document.querySelectorAll('.post-nav-button');
                navButtons.forEach(btn => btn.style.display = 'none');
                return;
            }}
            
            let currentPostIndex = 0;
            
            // Find which post is currently in view
            function findCurrentPostIndex() {{
                const viewportTop = window.scrollY + 100; // Offset for header
                let closestIndex = 0;
                let closestDistance = Infinity;
                
                posts.forEach((post, index) => {{
                    const rect = post.getBoundingClientRect();
                    const postTop = rect.top + window.scrollY;
                    const distance = Math.abs(postTop - viewportTop);
                    
                    if (distance < closestDistance) {{
                        closestDistance = distance;
                        closestIndex = index;
                    }}
                }});
                
                return closestIndex;
            }}
            
            // Update active post based on scroll position
            function updateActivePost() {{
                const newIndex = findCurrentPostIndex();
                if (newIndex !== currentPostIndex) {{
                    currentPostIndex = newIndex;
                    posts.forEach(post => post.classList.remove('active-post'));
                    if (posts[currentPostIndex]) {{
                        posts[currentPostIndex].classList.add('active-post');
                    }}
                    updateNavigation();
                }}
            }}
            
            // Update navigation button states
            function updateNavigation() {{
                const prevBtn = document.getElementById('nav-prev');
                const nextBtn = document.getElementById('nav-next');
                
                // Show/hide Previous button
                if (prevBtn) {{
                    prevBtn.style.display = currentPostIndex === 0 ? 'none' : 'flex';
                    prevBtn.classList.toggle('disabled', currentPostIndex === 0);
                }}
                
                // Show/hide Next button
                if (nextBtn) {{
                    nextBtn.style.display = currentPostIndex >= totalPosts - 1 ? 'none' : 'flex';
                    nextBtn.classList.toggle('disabled', currentPostIndex >= totalPosts - 1);
                }}
            }}
            
            // Navigate to a specific post
            function navigateToPost(index) {{
                if (index < 0 || index >= totalPosts) return;
                
                // Remove active class from all posts
                posts.forEach(post => post.classList.remove('active-post'));
                
                // Set current post as active
                posts[index].classList.add('active-post');
                
                // Scroll to post with smooth behavior
                const headerOffset = 120;
                const elementPosition = posts[index].getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                
                window.scrollTo({{ behavior: 'smooth', top: offsetPosition }});
                
                currentPostIndex = index;
                updateNavigation();
            }}
            
            // Previous button handler
            const prevBtn = document.getElementById('nav-prev');
            if (prevBtn) {{
                prevBtn.addEventListener('click', (e) => {{
                    e.preventDefault();
                    if (currentPostIndex > 0) {{
                        navigateToPost(currentPostIndex - 1);
                    }}
                }});
            }}
            
            // Next button handler
            const nextBtn = document.getElementById('nav-next');
            if (nextBtn) {{
                nextBtn.addEventListener('click', (e) => {{
                    e.preventDefault();
                    if (currentPostIndex < totalPosts - 1) {{
                        navigateToPost(currentPostIndex + 1);
                    }}
                }});
            }}
            
            // Initialize: set first post as active
            if (posts.length > 0) {{
                updateActivePost();
                updateNavigation();
            }}
            
            // Update active post on scroll (throttled)
            let scrollTimeout;
            window.addEventListener('scroll', () => {{
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(updateActivePost, 100);
            }}, {{ passive: true }});
            
            // Keyboard navigation support
            document.addEventListener('keydown', (e) => {{
                // Don't intercept if user is typing in an input/textarea
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
                    return;
                }}
                if (e.key === 'ArrowLeft' && currentPostIndex > 0) {{
                    e.preventDefault();
                    navigateToPost(currentPostIndex - 1);
                }} else if (e.key === 'ArrowRight' && currentPostIndex < totalPosts - 1) {{
                    e.preventDefault();
                    navigateToPost(currentPostIndex + 1);
                }}
            }});
        }}
        
        // Initialize navigation when DOM is ready
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initPostNavigation);
        }} else {{
            initPostNavigation();
        }}
        
        // Vote handling functions
        const VOTE_API_URL = 'http://localhost:5000/api/vote';  // Default vote API URL
        const isGitHubPages = window.location.hostname.includes('github.io');
        
        // Generate or get vote session cookie
        function getVoteSessionId() {{
            let sessionId = document.cookie.split('; ').find(row => row.startsWith('vote_session_id='));
            if (!sessionId) {{
                sessionId = 'vote_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
                document.cookie = 'vote_session_id=' + sessionId + '; path=/; max-age=31536000'; // 1 year
            }} else {{
                sessionId = sessionId.split('=')[1];
            }}
            return sessionId;
        }}
        
        // Get votes from localStorage
        function getLocalVotes() {{
            try {{
                const stored = localStorage.getItem('pending_votes');
                return stored ? JSON.parse(stored) : [];
            }} catch (e) {{
                return [];
            }}
        }}
        
        // Save vote to localStorage
        function saveVoteToLocal(postId, voteType, voteValue, voterCookie) {{
            const votes = getLocalVotes();
            const voteKey = `${{postId}}_${{voteType}}`;
            
            // Check if already voted
            if (votes.some(v => v.post_id === postId && v.vote_type === voteType && v.voter_cookie === voterCookie)) {{
                return false;
            }}
            
            votes.push({{
                post_id: postId,
                vote_type: voteType,
                vote_value: voteValue,
                voter_cookie: voterCookie,
                created_at: new Date().toISOString()
            }});
            
            localStorage.setItem('pending_votes', JSON.stringify(votes));
            return true;
        }}
        
        // Show vote stats for a specific vote type
        function showVoteStats(postId, voteType) {{
            const voteSection = document.querySelector(`.vote-section[data-post-id="${{postId}}"]`);
            if (!voteSection) {{
                console.warn('Could not find vote-section for post', postId);
                return;
            }}
            
            // Show all vote counts and percentages for this vote type
            const counts = voteSection.querySelectorAll(`#${{voteType}}-positive-count-${{postId}}, #${{voteType}}-negative-count-${{postId}}`);
            const percentages = voteSection.querySelectorAll(`#${{voteType}}-positive-pct-${{postId}}, #${{voteType}}-negative-pct-${{postId}}`);
            
            console.log('Showing vote stats for', voteType, 'post', postId, 'counts:', counts.length, 'percentages:', percentages.length);
            
            counts.forEach(el => {{
                if (el) {{
                    el.classList.remove('vote-stats-hidden');
                    el.style.display = ''; // Reset display to ensure visibility
                    console.log('Showing count element:', el.id, el.textContent);
                }}
            }});
            percentages.forEach(el => {{
                if (el) {{
                    el.classList.remove('vote-stats-hidden');
                    el.style.display = ''; // Reset display to ensure visibility
                    console.log('Showing percentage element:', el.id, el.textContent);
                }}
            }});
        }}
        
        // Show vote success indicator (tick icon + "投票成功")
        function showVoteSuccessIndicator(button) {{
            // Find the vote-item container (parent of vote-options)
            const voteItem = button.closest('.vote-item');
            if (!voteItem) {{
                console.warn('Could not find vote-item container');
                return;
            }}
            
            // Check if indicator already exists for this button
            const existingIndicator = voteItem.querySelector(`.vote-success-indicator[data-button-id="${{button.id || button.getAttribute('data-vote-value')}}"]`);
            if (existingIndicator) {{
                return;
            }}
            
            // Create success indicator element
            const indicator = document.createElement('span');
            indicator.className = 'vote-success-indicator';
            indicator.setAttribute('data-button-id', button.id || button.getAttribute('data-vote-value'));
            indicator.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 3L4.5 8.5L2 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>投票成功</span>
            `;
            
            // Append to vote-item (will be positioned absolutely relative to vote-item)
            voteItem.appendChild(indicator);
            
            // Position it vertically centered relative to the specific button
            const buttonRect = button.getBoundingClientRect();
            const itemRect = voteItem.getBoundingClientRect();
            const relativeTop = buttonRect.top - itemRect.top + (buttonRect.height / 2);
            indicator.style.top = relativeTop + 'px';
        }}
        
        // Update vote counts optimistically (for GitHub Pages)
        function updateVoteCountOptimistic(postId, voteType, voteValue) {{
            // Get current counts
            const positiveEl = document.getElementById(`${{voteType}}-positive-count-${{postId}}`);
            const negativeEl = document.getElementById(`${{voteType}}-negative-count-${{postId}}`);
            
            if (positiveEl && negativeEl) {{
                // Parse counts, removing "票" suffix if present
                let positiveCount = parseInt(positiveEl.textContent.replace('票', '').trim()) || 0;
                let negativeCount = parseInt(negativeEl.textContent.replace('票', '').trim()) || 0;
                
                // Increment the voted option
                if (voteValue === 'positive') {{
                    positiveCount++;
                }} else {{
                    negativeCount++;
                }}
                
                const total = positiveCount + negativeCount;
                const positivePct = total > 0 ? (positiveCount / total * 100).toFixed(1) : 0;
                const negativePct = total > 0 ? (negativeCount / total * 100).toFixed(1) : 0;
                
                // Update display
                positiveEl.textContent = positiveCount + '票';
                document.getElementById(`${{voteType}}-positive-pct-${{postId}}`).textContent = positivePct + '%';
                negativeEl.textContent = negativeCount + '票';
                document.getElementById(`${{voteType}}-negative-pct-${{postId}}`).textContent = negativePct + '%';
                
                // Show stats after voting
                showVoteStats(postId, voteType);
            }}
        }}
        
        // Handle vote button click
        function handleVote(button) {{
            const postId = parseInt(button.getAttribute('data-post-id'));
            const voteType = button.getAttribute('data-vote-type');
            const voteValue = button.getAttribute('data-vote-value');
            const voterCookie = getVoteSessionId();
            
            // Disable button temporarily
            button.disabled = true;
            button.style.opacity = '0.6';
            
            // Check if already voted (check localStorage for GitHub Pages)
            if (isGitHubPages) {{
                const votes = getLocalVotes();
                if (votes.some(v => v.post_id === postId && v.vote_type === voteType && v.voter_cookie === voterCookie)) {{
                    alert('您已經投過票了！');
                    button.disabled = false;
                    button.style.opacity = '1';
                    return;
                }}
            }}
            
            // If on GitHub Pages, use localStorage
            if (isGitHubPages) {{
                if (saveVoteToLocal(postId, voteType, voteValue, voterCookie)) {{
                    // Update UI optimistically (this also shows stats)
                    updateVoteCountOptimistic(postId, voteType, voteValue);
                    
                    // Disable all vote buttons for this vote type
                    const voteSection = button.closest('.vote-section');
                    const buttons = voteSection.querySelectorAll(`[data-vote-type="${{voteType}}"]`);
                    buttons.forEach(btn => {{
                        btn.disabled = true;
                        btn.style.opacity = '0.6';
                    }});
                    
                    // Show success indicator on the voted button
                    showVoteSuccessIndicator(button);
                    
                    // Show success message
                    console.log('✅ Vote saved locally. It will be processed by GitHub Actions.');
                }} else {{
                    alert('您已經投過票了！');
                    button.disabled = false;
                    button.style.opacity = '1';
                }}
                return;
            }}
            
            // For localhost, use API
            fetch(VOTE_API_URL, {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{
                    post_id: postId,
                    vote_type: voteType,
                    vote_value: voteValue,
                    voter_cookie: voterCookie
                }})
            }})
            .then(response => {{
                if (response.status === 409) {{
                    alert('您已經投過票了！');
                    button.disabled = false;
                    button.style.opacity = '1';
                    return null;
                }}
                
                if (!response.ok) {{
                    return response.json().then(data => {{
                        throw new Error(data.error || `HTTP ${{response.status}}: ${{response.statusText}}`);
                    }}).catch(() => {{
                        throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                    }});
                }}
                
                return response.json();
            }})
            .then(data => {{
                if (!data) return; // Already handled (409 case)
                
                if (data.success && data.stats) {{
                    updateVoteDisplay(postId, voteType, data.stats);
                    // Show vote stats after voting
                    showVoteStats(postId, voteType);
                    // Disable all vote buttons for this vote type
                    const voteSection = button.closest('.vote-section');
                    const buttons = voteSection.querySelectorAll(`[data-vote-type="${{voteType}}"]`);
                    buttons.forEach(btn => {{
                        btn.disabled = true;
                        btn.style.opacity = '0.6';
                    }});
                    
                    // Show success indicator on the voted button
                    showVoteSuccessIndicator(button);
                }} else {{
                    alert('投票失敗，請稍後再試');
                    button.disabled = false;
                    button.style.opacity = '1';
                }}
            }})
            .catch(error => {{
                console.error('Vote error:', error);
                
                let errorMessage = '投票失敗，請稍後再試';
                
                if (error.message && error.message.includes('Failed to fetch')) {{
                    errorMessage = '無法連接到投票伺服器。請確認投票伺服器是否正在運行（執行 uv run python/vote_server_local.py）。\\n\\n提示：如果使用 file:// 打開網頁，請改用 HTTP 伺服器（例如：uv run python -m http.server 8000）';
                }} else if (error.message && error.message.includes('HTTP')) {{
                    errorMessage = `投票失敗：${{error.message}}`;
                }} else if (error.message) {{
                    errorMessage = `投票失敗：${{error.message}}`;
                }}
                
                alert(errorMessage);
                button.disabled = false;
                button.style.opacity = '1';
            }});
        }}
        
        // Update vote display with new statistics
        function updateVoteDisplay(postId, voteType, stats) {{
            const typeStats = stats[voteType];
            const total = typeStats.total;
            const positive = typeStats.positive;
            const negative = typeStats.negative;
            
            const positivePct = total > 0 ? (positive / total * 100).toFixed(1) : 0;
            const negativePct = total > 0 ? (negative / total * 100).toFixed(1) : 0;
            
            // Update counts and percentages
            document.getElementById(`${{voteType}}-positive-count-${{postId}}`).textContent = positive + '票';
            document.getElementById(`${{voteType}}-positive-pct-${{postId}}`).textContent = positivePct + '%';
            document.getElementById(`${{voteType}}-negative-count-${{postId}}`).textContent = negative + '票';
            document.getElementById(`${{voteType}}-negative-pct-${{postId}}`).textContent = negativePct + '%';
        }}
        
        // Load vote stats from JSON file (for GitHub Pages) or API (for localhost)
        function loadVoteStats(postId, voteType) {{
            return new Promise((resolve) => {{
                if (isGitHubPages) {{
                    // For GitHub Pages, try to load from votes.json
                    fetch('votes/votes.json')
                        .then(response => {{
                            if (!response.ok) {{
                                resolve(null);
                                return;
                            }}
                            return response.json();
                        }})
                        .then(data => {{
                            if (!data) {{
                                resolve(null);
                                return;
                            }}
                            const postKey = String(postId);
                            if (data[postKey] && data[postKey][voteType]) {{
                                const votes = data[postKey][voteType];
                                const stats = {{
                                    positive: votes.filter(v => v.vote_value === 'positive').length,
                                    negative: votes.filter(v => v.vote_value === 'negative').length
                                }};
                                stats.total = stats.positive + stats.negative;
                                resolve({{ [voteType]: stats }});
                            }} else {{
                                resolve(null);
                            }}
                        }})
                        .catch(() => resolve(null));
                }} else {{
                    // For localhost, use API
                    fetch(`http://localhost:5000/api/vote/stats/${{postId}}`)
                        .then(response => {{
                            if (!response.ok) {{
                                resolve(null);
                                return;
                            }}
                            return response.json();
                        }})
                        .then(data => {{
                            resolve(data);
                        }})
                        .catch(() => resolve(null));
                }}
            }});
        }}
        
        // Check vote status for all posts on page load
        async function checkVoteStatusOnLoad() {{
            const voteSections = document.querySelectorAll('.vote-section');
            const voterCookie = getVoteSessionId();
            
            // Use Promise.all to wait for all async operations
            const promises = Array.from(voteSections).map(async section => {{
                const postId = parseInt(section.getAttribute('data-post-id'));
                if (!postId) return;
                
                // For GitHub Pages, check localStorage
                if (isGitHubPages) {{
                    const votes = getLocalVotes();
                    const stockVote = votes.find(v => v.post_id === postId && v.vote_type === 'stock' && v.voter_cookie === voterCookie);
                    const optionsVote = votes.find(v => v.post_id === postId && v.vote_type === 'options' && v.voter_cookie === voterCookie);
                    
                    // Load and display stock vote stats if voted
                    if (stockVote) {{
                        console.log('Found stock vote for post', postId, 'value:', stockVote.vote_value);
                        
                        // Try to load stats from votes.json first
                        let stats = await loadVoteStats(postId, 'stock');
                        console.log('Loaded stats from votes.json:', stats);
                        
                        // If no stats found, calculate from localStorage pending votes
                        if (!stats || !stats.stock) {{
                            const pendingVotes = votes.filter(v => v.post_id === postId && v.vote_type === 'stock');
                            const positiveCount = pendingVotes.filter(v => v.vote_value === 'positive').length;
                            const negativeCount = pendingVotes.filter(v => v.vote_value === 'negative').length;
                            const total = positiveCount + negativeCount;
                            if (total > 0) {{
                                stats = {{
                                    stock: {{
                                        positive: positiveCount,
                                        negative: negativeCount,
                                        total: total
                                    }}
                                }};
                                console.log('Calculated stats from localStorage:', stats);
                            }}
                        }}
                        
                        if (stats && stats.stock) {{
                            updateVoteDisplay(postId, 'stock', stats);
                        }}
                        showVoteStats(postId, 'stock');
                        
                        // Show success indicator on the voted button
                        const votedButton = section.querySelector(`[data-vote-type="stock"][data-vote-value="${{stockVote.vote_value}}"]`);
                        console.log('Found voted button:', votedButton);
                        if (votedButton) {{
                            showVoteSuccessIndicator(votedButton);
                            // Disable all stock vote buttons
                            const buttons = section.querySelectorAll(`[data-vote-type="stock"]`);
                            buttons.forEach(btn => {{
                                btn.disabled = true;
                                btn.style.opacity = '0.6';
                            }});
                        }}
                    }}
                    
                    // Load and display options vote stats if voted
                    if (optionsVote) {{
                        console.log('Found options vote for post', postId, 'value:', optionsVote.vote_value);
                        
                        // Try to load stats from votes.json first
                        let stats = await loadVoteStats(postId, 'options');
                        console.log('Loaded stats from votes.json:', stats);
                        
                        // If no stats found, calculate from localStorage pending votes
                        if (!stats || !stats.options) {{
                            const pendingVotes = votes.filter(v => v.post_id === postId && v.vote_type === 'options');
                            const positiveCount = pendingVotes.filter(v => v.vote_value === 'positive').length;
                            const negativeCount = pendingVotes.filter(v => v.vote_value === 'negative').length;
                            const total = positiveCount + negativeCount;
                            if (total > 0) {{
                                stats = {{
                                    options: {{
                                        positive: positiveCount,
                                        negative: negativeCount,
                                        total: total
                                    }}
                                }};
                                console.log('Calculated stats from localStorage:', stats);
                            }}
                        }}
                        
                        if (stats && stats.options) {{
                            updateVoteDisplay(postId, 'options', stats);
                        }}
                        showVoteStats(postId, 'options');
                        
                        // Show success indicator on the voted button
                        const votedButton = section.querySelector(`[data-vote-type="options"][data-vote-value="${{optionsVote.vote_value}}"]`);
                        console.log('Found voted button:', votedButton);
                        if (votedButton) {{
                            showVoteSuccessIndicator(votedButton);
                            // Disable all options vote buttons
                            const buttons = section.querySelectorAll(`[data-vote-type="options"]`);
                            buttons.forEach(btn => {{
                                btn.disabled = true;
                                btn.style.opacity = '0.6';
                            }});
                        }}
                    }}
                }} else {{
                    // For localhost, check localStorage first (fallback), then try API
                    const votes = getLocalVotes();
                    const stockVote = votes.find(v => v.post_id === postId && v.vote_type === 'stock' && v.voter_cookie === voterCookie);
                    const optionsVote = votes.find(v => v.post_id === postId && v.vote_type === 'options' && v.voter_cookie === voterCookie);
                    
                    // If found in localStorage, use that (for when API is not running)
                    if (stockVote || optionsVote) {{
                        if (stockVote) {{
                            // Try to load stats from API first
                            let stats = await loadVoteStats(postId, 'stock');
                            
                            // If no stats from API, calculate from localStorage
                            if (!stats || !stats.stock) {{
                                const pendingVotes = votes.filter(v => v.post_id === postId && v.vote_type === 'stock');
                                const positiveCount = pendingVotes.filter(v => v.vote_value === 'positive').length;
                                const negativeCount = pendingVotes.filter(v => v.vote_value === 'negative').length;
                                const total = positiveCount + negativeCount;
                                if (total > 0) {{
                                    stats = {{
                                        stock: {{
                                            positive: positiveCount,
                                            negative: negativeCount,
                                            total: total
                                        }}
                                    }};
                                }}
                            }}
                            
                            if (stats && stats.stock) {{
                                updateVoteDisplay(postId, 'stock', stats);
                            }}
                            showVoteStats(postId, 'stock');
                            
                            const votedButton = section.querySelector(`[data-vote-type="stock"][data-vote-value="${{stockVote.vote_value}}"]`);
                            if (votedButton) {{
                                showVoteSuccessIndicator(votedButton);
                                const buttons = section.querySelectorAll(`[data-vote-type="stock"]`);
                                buttons.forEach(btn => {{
                                    btn.disabled = true;
                                    btn.style.opacity = '0.6';
                                }});
                            }}
                        }}
                        
                        if (optionsVote) {{
                            // Try to load stats from API first
                            let stats = await loadVoteStats(postId, 'options');
                            
                            // If no stats from API, calculate from localStorage
                            if (!stats || !stats.options) {{
                                const pendingVotes = votes.filter(v => v.post_id === postId && v.vote_type === 'options');
                                const positiveCount = pendingVotes.filter(v => v.vote_value === 'positive').length;
                                const negativeCount = pendingVotes.filter(v => v.vote_value === 'negative').length;
                                const total = positiveCount + negativeCount;
                                if (total > 0) {{
                                    stats = {{
                                        options: {{
                                            positive: positiveCount,
                                            negative: negativeCount,
                                            total: total
                                        }}
                                    }};
                                }}
                            }}
                            
                            if (stats && stats.options) {{
                                updateVoteDisplay(postId, 'options', stats);
                            }}
                            showVoteStats(postId, 'options');
                            
                            const votedButton = section.querySelector(`[data-vote-type="options"][data-vote-value="${{optionsVote.vote_value}}"]`);
                            if (votedButton) {{
                                showVoteSuccessIndicator(votedButton);
                                const buttons = section.querySelectorAll(`[data-vote-type="options"]`);
                                buttons.forEach(btn => {{
                                    btn.disabled = true;
                                    btn.style.opacity = '0.6';
                                }});
                            }}
                        }}
                    }} else {{
                        // If not in localStorage, try API (for votes stored in database)
                        const CHECK_API_URL = 'http://localhost:5000/api/vote/check/';
                        try {{
                            const response = await fetch(CHECK_API_URL + postId);
                            if (!response.ok) return;
                            const data = await response.json();
                            if (!data) return;
                            
                            if (data.stock_voted) {{
                                // Load stats and update display
                                const stats = await loadVoteStats(postId, 'stock');
                                if (stats && stats.stock) {{
                                    updateVoteDisplay(postId, 'stock', stats);
                                }}
                                showVoteStats(postId, 'stock');
                                // Show success indicator on the voted button
                                const votedButton = section.querySelector(`[data-vote-type="stock"][data-vote-value="${{data.stock_vote_value}}"]`);
                                if (votedButton) {{
                                    showVoteSuccessIndicator(votedButton);
                                    // Disable all stock vote buttons
                                    const buttons = section.querySelectorAll(`[data-vote-type="stock"]`);
                                    buttons.forEach(btn => {{
                                        btn.disabled = true;
                                        btn.style.opacity = '0.6';
                                    }});
                                }}
                            }}
                            if (data.options_voted) {{
                                // Load stats and update display
                                const stats = await loadVoteStats(postId, 'options');
                                if (stats && stats.options) {{
                                    updateVoteDisplay(postId, 'options', stats);
                                }}
                                showVoteStats(postId, 'options');
                                // Show success indicator on the voted button
                                const votedButton = section.querySelector(`[data-vote-type="options"][data-vote-value="${{data.options_vote_value}}"]`);
                                if (votedButton) {{
                                    showVoteSuccessIndicator(votedButton);
                                    // Disable all options vote buttons
                                    const buttons = section.querySelectorAll(`[data-vote-type="options"]`);
                                    buttons.forEach(btn => {{
                                        btn.disabled = true;
                                        btn.style.opacity = '0.6';
                                    }});
                                }}
                            }}
                        }} catch (error) {{
                            // Silently fail - API might not be running
                            console.debug('Could not check vote status via API:', error);
                        }}
                    }}
                }}
            }});
            
            // Wait for all checks to complete
            await Promise.all(promises);
        }}
        
        // Initialize vote status check on page load
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', checkVoteStatusOnLoad);
        }} else {{
            checkVoteStatusOnLoad();
        }}
    </script>
    <script src="infinite-scroll.js"></script>
    <script src="timeline-indicator.js"></script>
    
    <!-- Post Navigation Buttons -->
    <div class="post-navigation">
        <button id="nav-prev" class="post-nav-button post-nav-prev" aria-label="Previous Post">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 18L9 12L15 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </button>
        <button id="nav-next" class="post-nav-button post-nav-next" aria-label="Next Post">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </button>
    </div>
</body>
</html>
'''
    
    return html


def main():
    """Main function to generate the website"""
    print("🚀 AI Trader Website Generator")
    print("=" * 80)
    
    # Sync votes from SQLite to JSON first
    print("\n🔄 Syncing votes from SQLite to JSON...")
    sync_votes_from_sqlite_to_json()
    
    # Check if database exists
    if not os.path.exists(MEMORY_DB):
        print(f"❌ Database not found: {MEMORY_DB}")
        print("   Please run truthsocial1.py first to generate analyses.")
        return
    
    print(f"📊 Reading analyses from database: {MEMORY_DB}")
    posts = get_all_analyses()
    
    if not posts:
        print("⚠️  No analyses found in database.")
        print("   Generating empty page...")
    else:
        print(f"✅ Found {len(posts)} analyses")
    
    print(f"\n🔨 Generating HTML...")
    html = generate_html_page(posts)
    
    # Write to file (one level up from python/ to AITrader/)
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Generated: {output_path}")
    print(f"\n📋 Summary:")
    print(f"   • Total posts: {len(posts)}")
    print(f"   • Posts per batch: {POSTS_PER_BATCH}")
    print(f"   • Initial visible: {POSTS_PER_BATCH * INITIAL_VISIBLE_BATCHES}")
    print(f"   • Lazy loaded: {max(0, len(posts) - POSTS_PER_BATCH * INITIAL_VISIBLE_BATCHES)}")
    print(f"\n🌐 Next steps:")
    print(f"   1. Add image files to AITrader/assets/ folder:")
    print(f"      - trump_icon.jpg (poster icon)")
    print(f"      - truth_logo.png (Truth Social logo)")
    print(f"   2. Open index.html in browser to preview")
    print(f"   3. Deploy to GitHub Pages")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

