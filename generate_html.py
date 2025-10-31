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

# Add parent directory to path to import database modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

# Get the correct database path (in parent directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
MEMORY_DB = os.path.join(PARENT_DIR, "truthsocial_memory.db")

# Configuration
POSTS_PER_BATCH = 5
INITIAL_VISIBLE_BATCHES = 1  # Show first 5 posts immediately
MAX_POSTS_ON_MAIN_PAGE = 30  # Limit main page to recent 30 posts
OUTPUT_FILE = "index.html"

# Fixed metadata
POSTER_NAME = "Donald J. Trump"
POSTER_ID = "@realDonaldTrump"


def get_all_analyses(limit: int = MAX_POSTS_ON_MAIN_PAGE) -> List[Dict]:
    """
    Get all post analyses from memory database, newest first
    Returns list of dicts with post info and all AI outputs
    """
    with sqlite3.connect(MEMORY_DB) as conn:
        cursor = conn.cursor()
        
        # First get the post IDs we want (limited)
        cursor.execute('''
            SELECT id FROM posts 
            ORDER BY post_date DESC 
            LIMIT ?
        ''', (limit,))
        post_ids = [row[0] for row in cursor.fetchall()]
        
        if not post_ids:
            return []
        
        # Now get all data for these posts
        placeholders = ','.join('?' * len(post_ids))
        cursor.execute(f'''
            SELECT 
                p.id, p.post_date, p.post_content,
                ao.ai_type, ao.ai_name, ao.output_content, ao.created_at
            FROM posts p
            LEFT JOIN ai_outputs ao ON p.id = ao.post_id
            WHERE p.id IN ({placeholders})
            ORDER BY p.post_date DESC, ao.ai_type DESC
        ''', post_ids)
        
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        # Group by post
        posts_dict = {}
        for row in rows:
            post_id, post_date, post_content, ai_type, ai_name, output_content, analysis_date = row
            
            if post_id not in posts_dict:
                posts_dict[post_id] = {
                    'id': post_id,
                    'post_date': post_date,
                    'post_content': post_content,
                    'openai_output': None,
                    'deepseek_output': None,
                    'evaluator_output': None,
                    'analysis_date': None
                }
            
            # Assign outputs based on AI name
            if ai_name == 'OpenAI_Advisor':
                posts_dict[post_id]['openai_output'] = output_content
            elif ai_name == 'DeepSeek_Advisor':
                posts_dict[post_id]['deepseek_output'] = output_content
            elif ai_name == 'TradeEvaluator':
                posts_dict[post_id]['evaluator_output'] = output_content
                # Use the evaluator's creation time as the analysis date
                if analysis_date:
                    posts_dict[post_id]['analysis_date'] = analysis_date
        
        # Convert to list and sort by date
        posts_list = list(posts_dict.values())
        posts_list.sort(key=lambda x: x['post_date'], reverse=True)
        
        return posts_list[:limit]


def parse_stock_picks(text: str, is_cantonese: bool = False) -> List[Dict]:
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
        r'\*\*STOCK PICKS[^:]*:\*\*(.+?)(?:\*\*OPTIONS PICKS|\*\*期權推薦|$)',
        r'\*\*股票推薦[^:]*:\*\*(.+?)(?:\*\*OPTIONS|\*\*期權|$)',
    ]
    
    stock_section = None
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            stock_section = match.group(1)
            break
    
    if not stock_section:
        return []
    
    # Check for PASS (no recommendations)
    if re.search(r'PASS|無推薦|沒有推薦', stock_section, re.IGNORECASE):
        return []
    
    # Extract "Top 1", "Top 2", "Top 3" picks
    # Pattern: **Top 1: TICKER (optional name)** - BUY/SELL/PASS
    top_patterns = [
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})(?:\s*\([^)]+\))?\*\*\s*[-–]\s*(BUY|SELL|PASS|買入|賣出)',
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})(?:\s*\([^)]+\))?\*\*\s*[-–]?\s*(BUY|SELL|PASS|買入|賣出)',
        r'(?:^|\n)(\d+)\.\s*\*\*([A-Z]{2,5})(?:\s*\([^)]+\))?\*\*\s*[-–]\s*(BUY|SELL|PASS|買入|賣出)',
    ]
    
    for pattern in top_patterns:
        matches = re.finditer(pattern, stock_section, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            top_num = int(match.group(1))
            ticker = match.group(2)
            action = match.group(3).upper()
            
            # Skip false positives
            if ticker in ['BUY', 'SELL', 'CALL', 'PUT', 'ETF', 'PASS', 'TOP']:
                continue
            
            # Translate Cantonese actions
            if action == '買入':
                action = 'BUY'
            elif action == '賣出':
                action = 'SELL'
            
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


def parse_options_picks(text: str, is_cantonese: bool = False) -> List[Dict]:
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
        r'\*\*OPTIONS PICKS[^:]*:\*\*(.+?)(?:\*\*FINAL VERDICT|\*\*最終裁決|$)',
        r'\*\*期權推薦[^:]*:\*\*(.+?)(?:\*\*FINAL|\*\*最終|$)',
    ]
    
    options_section = None
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            options_section = match.group(1)
            break
    
    if not options_section:
        return []
    
    # Check for PASS (no recommendations)
    if re.search(r'PASS|無推薦|沒有推薦', options_section, re.IGNORECASE):
        return []
    
    # Extract "Top 1", "Top 2", "Top 3" picks
    # Pattern: **Top 1: TICKER CALL/PUT** at $strike exp date
    top_patterns = [
        r'\*\*Top\s*(\d+)[:\s]+([A-Z]{2,5})\s+(CALL|PUT|PASS|認購|認沽)\*\*\s*(?:at\s*\$(\d+))?\s*(?:exp\s+([^<\n]+))?',
        r'(?:^|\n)(\d+)\.\s*\*\*([A-Z]{2,5})\s+(CALL|PUT|PASS|認購|認沽)\*\*\s*(?:at\s*\$(\d+))?\s*(?:exp\s+([^<\n]+))?',
    ]
    
    for pattern in top_patterns:
        matches = re.finditer(pattern, options_section, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            top_num = int(match.group(1))
            ticker = match.group(2)
            option_type = match.group(3).upper()
            strike = match.group(4) if len(match.groups()) >= 4 and match.group(4) else '?'
            expiry = match.group(5).strip() if len(match.groups()) >= 5 and match.group(5) else ''
            
            # Skip false positives
            if ticker in ['CALL', 'PUT', 'ETF', 'PASS', 'TOP']:
                continue
            
            # Translate Cantonese
            if option_type == '認購':
                option_type = 'CALL'
            elif option_type == '認沽':
                option_type = 'PUT'
            
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
    """Detect if text is primarily Cantonese/Chinese"""
    if not text:
        return 'en'
    # Simple heuristic: if more than 30% Chinese characters, consider it Chinese
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.replace(' ', ''))
    return 'zh' if (total_chars > 0 and chinese_chars / total_chars > 0.3) else 'en'


def simple_markdown_to_html(text: str) -> str:
    """
    Convert simple markdown to HTML
    Handles: **bold**, bullet lists, line breaks
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
        r'\*\*STOCK PICKS[^:]*:\*\*(.+?)(?:\*\*OPTIONS PICKS|\*\*期權推薦|$)',
        r'\*\*股票推薦[^:]*:\*\*(.+?)(?:\*\*OPTIONS|\*\*期權|$)',
    ]
    for pattern in stock_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            stock_section = match.group(1).strip()
            break
    
    # Extract OPTIONS PICKS section
    options_section = ''
    options_patterns = [
        r'\*\*OPTIONS PICKS[^:]*:\*\*(.+?)(?:\*\*FINAL VERDICT|\*\*最終裁決|$)',
        r'\*\*期權推薦[^:]*:\*\*(.+?)(?:\*\*FINAL|\*\*最終|$)',
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
        r'\*\*最終裁決[^:]*:\*\*(.+?)$',
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
        # Remove Cantonese meta sentence at end
        section_text = re.sub(r'[（(]?以上.*?粵語.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'[（(]?.*?符合語言要求.*?[）)]?\.?$', '', section_text, flags=re.MULTILINE)
        return section_text.strip()
    
    return {
        'stock_picks': clean_section(stock_section) or 'No stock recommendations available.',
        'options_picks': clean_section(options_section) or 'No options recommendations available.',
        'final_verdict': clean_section(verdict_section) or 'No final verdict available.'
    }


def generate_post_card_html(post: Dict, batch_num: int, is_visible: bool = False) -> str:
    """Generate HTML for a single post card"""
    
    # Detect language from evaluator output (final recommendation)
    evaluator_text = post.get('evaluator_output', '') or ''
    is_cantonese = detect_language(evaluator_text)
    
    # Parse stock and options picks from evaluator output
    stocks = parse_stock_picks(evaluator_text, is_cantonese)
    options = parse_options_picks(evaluator_text, is_cantonese)
    
    # Format datetime
    formatted_date = format_datetime(post['post_date'])
    
    # Format analysis date
    analysis_date = post.get('analysis_date')
    if analysis_date:
        formatted_analysis_date = format_datetime(analysis_date)
        analysis_date_label = "分析日期" if is_cantonese == 'zh' else "Analysis Date"
        analysis_date_html = f'<div class="analysis-date" style="text-align: left;">{analysis_date_label}: {formatted_analysis_date}</div>'
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
            action_text = '買入 (BUY)' if is_cantonese == 'zh' else 'BUY'
            action_class = 'card-action-buy'
        else:  # SELL
            action_text = '賣出 (SELL)' if is_cantonese == 'zh' else 'SELL'
            action_class = 'card-action-sell'
        
        stock_card_html = f'''
        <div class="summary-card">
            <div class="card-ticker">{primary_stock['ticker']}</div>
            <div class="card-action {action_class}">{action_text}</div>
        </div>
        '''
    else:
        nil_text = '無' if is_cantonese == 'zh' else 'NIL'
        stock_card_html = f'''
        <div class="summary-card empty">
            <div class="card-empty">{nil_text}</div>
        </div>
        '''
    
    option_card_html = ''
    if primary_option:
        # Determine language for labels
        best_buy_label = '最佳時機' if is_cantonese == 'zh' else 'Best Buy'
        target_label = '目標' if is_cantonese == 'zh' else 'Target'
        
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
        nil_text = '無' if is_cantonese == 'zh' else 'NIL'
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
    
    html = f'''
    <article class="post-card {visibility_class}" data-batch="{batch_num}">
        {analysis_date_html}
        <div class="post-header">
            <div class="header-left">
                <h2 class="section-title">Stock 股票</h2>
                {stock_card_html}
            </div>
            
            <div class="header-center">
                <h2 class="section-title">Options 期權</h2>
                {option_card_html}
            </div>
            
            <div class="header-right">
                <div class="truth-logo">
                    <img src="assets/truth_logo.png" alt="Truth Social" onerror="this.style.display='none'">
                </div>
                <div class="post-meta">
                    <img src="assets/trump_icon.jpg" alt="Trump" class="poster-icon" onerror="this.style.display='none'">
                    <div class="meta-text">
                        <div class="meta-date">Post Date: {formatted_date}</div>
                        <div class="meta-name">{POSTER_NAME}</div>
                        <div class="meta-id">{POSTER_ID}</div>
                    </div>
                </div>
                <div class="post-content">
                    {escape_html(post_content)}
                </div>
            </div>
        </div>
        
        <div class="post-body">
            <div class="analysis-section section-gray-1">
                <h3>📈 Stock Picks</h3>
                <div class="analysis-content">
                    {stock_picks_html}
                </div>
            </div>
            
            <div class="analysis-section section-gray-2">
                <h3>📊 Options Picks</h3>
                <div class="analysis-content">
                    {options_picks_html}
                </div>
            </div>
            
            <div class="analysis-section section-gray-1">
                <h3>🎯 Final Verdict</h3>
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
    <title>AI Trader - Truth Social Stock Analysis</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header class="main-header">
        <h1>TRUTH DOCK</h1>
        <p class="subtitle">Truth Social Stock Analysis</p>
    </header>
    
    <main id="posts-container">
        {posts_html}
    </main>
    
    <div id="loading-indicator" class="loading hidden">
        <div class="spinner"></div>
        <p>Loading more analyses...</p>
    </div>
    
    <div id="end-message" class="end-message hidden">
        <p>✓ All analyses loaded</p>
    </div>
    
    <footer class="main-footer">
        <p>Powered by TruthDock, all rights reserved.</p>
    </footer>
    
    <script>
        const TOTAL_BATCHES = {total_batches};
        const INITIAL_VISIBLE = {INITIAL_VISIBLE_BATCHES};
    </script>
    <script src="infinite-scroll.js"></script>
    <script src="timeline-indicator.js"></script>
</body>
</html>
'''
    
    return html


def main():
    """Main function to generate the website"""
    print("🚀 AI Trader Website Generator")
    print("=" * 80)
    
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
    
    # Write to file
    output_path = os.path.join(os.path.dirname(__file__), OUTPUT_FILE)
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

