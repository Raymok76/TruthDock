# Language System Guide - English / Cantonese

## 🌐 How Language Detection Works

The AI Trader website **automatically detects** the language from the AI evaluator's output and adapts the display accordingly. There is **NO manual switch** - it's completely automatic.

---

## 🤖 Language Flow

### 1. AI Analysis Stage (`truthsocial1.py`)

**Environment Variable Controls AI Language:**

```bash
# In your .env file:
TRUTHSOCIAL_CANTONESE=true   # AI outputs in Cantonese
TRUTHSOCIAL_CANTONESE=false  # AI outputs in English
```

**How It Works:**
- `truthsocial1.py` reads the `TRUTHSOCIAL_CANTONESE` setting
- Passes it to AI evaluator instructions
- AI generates output in specified language
- Output saved to database

### 2. Website Generation Stage (`generate_html.py`)

**Automatic Language Detection:**

```python
def detect_language(text: str) -> str:
    """Detect if text is primarily Cantonese/Chinese"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.replace(' ', ''))
    return 'zh' if (chinese_chars / total_chars > 0.3) else 'en'
```

- Analyzes the evaluator output text
- If >30% Chinese characters → Cantonese mode
- Otherwise → English mode

**What Changes Based on Language:**

| Element | English Mode | Cantonese Mode |
|---------|-------------|----------------|
| "NIL" label | NIL | 無 |
| "Best Buy" label | Best Buy | 最佳時機 |
| Stock action | BUY / SELL | 買入 (BUY) / 賣出 (SELL) |

---

## 📝 Complete Workflow

### Scenario A: Generate English Analysis

```bash
# 1. Set environment
echo "TRUTHSOCIAL_CANTONESE=false" >> .env

# 2. Run analysis
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py
# → AI generates English output
# → Saves to database

# 3. Generate website
cd AITrader
./update.sh
# → Detects English (< 30% Chinese chars)
# → Website uses English labels
```

**Result:**
- Stock card: "NIL" or "BUY/SELL"
- Options card: "Best Buy" label
- All sections in English

### Scenario B: Generate Cantonese Analysis

```bash
# 1. Set environment
echo "TRUTHSOCIAL_CANTONESE=true" >> .env

# 2. Run analysis
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py
# → AI generates Cantonese output
# → Saves to database

# 3. Generate website
cd AITrader
./update.sh
# → Detects Cantonese (> 30% Chinese chars)
# → Website uses Cantonese labels
```

**Result:**
- Stock card: "無" or "買入 (BUY)/賣出 (SELL)"
- Options card: "最佳時機" label
- All sections in Cantonese

---

## 🔧 How to Change Language

### Method 1: Environment Variable (Recommended)

**Check current setting:**
```bash
cd /home/raymok/projects/agents/6_mcp
cat .env | grep TRUTHSOCIAL_CANTONESE
```

**Change to English:**
```bash
# Edit .env file
nano .env
# Change line to:
TRUTHSOCIAL_CANTONESE=false
```

**Change to Cantonese:**
```bash
# Edit .env file
nano .env
# Change line to:
TRUTHSOCIAL_CANTONESE=true
```

**Apply changes:**
```bash
# Run new analysis with new language
uv run truthsocial1.py

# Regenerate website
cd AITrader
./update.sh
```

### Method 2: Override in Code

**Temporary override** (doesn't affect .env):

```python
# In truthsocial1.py, around line 103-105
openai_advisor = TruthSocialTrader(
    name="OpenAI_Advisor", 
    provider="openai", 
    use_cantonese=True  # ← Change this
)
```

---

## 🎨 UI Elements by Language

### English Mode Display:

```
Stock 股票
┌─────────┐
│   XOM   │
│   BUY   │  ← Green button
└─────────┘

Options 期權
┌──────────────┐
│     AXON     │
│     CALL     │  ← Green button
│              │
│   Best Buy   │  ← Label
│     ▼        │
│━━━━━━━━━━━━│
│     $800     │
└──────────────┘
```

### Cantonese Mode Display:

```
Stock 股票
┌─────────┐
│   XOM   │
│ 買入(BUY)│  ← Green button
└─────────┘

Options 期權
┌──────────────┐
│     AXON     │
│     CALL     │  ← Green button
│              │
│   最佳時機    │  ← Label
│     ▼        │
│━━━━━━━━━━━━│
│     $800     │
└──────────────┘
```

---

## 📊 Language Detection Logic

### Code Location:
`generate_html.py` lines 264-271

### How It Works:

```python
# Example 1: English text
text = "Buy XOM stock because energy sector is strong"
chinese_chars = 0
total_chars = 42
percentage = 0% → Language: 'en'

# Example 2: Cantonese text  
text = "買入XOM股票因為能源板塊強勁"
chinese_chars = 12
total_chars = 16
percentage = 75% → Language: 'zh'

# Example 3: Mixed (still detects as Cantonese)
text = "買入 (BUY) XOM 股票"
chinese_chars = 4
total_chars = 11
percentage = 36% → Language: 'zh'
```

**Threshold:** 30% Chinese characters = Cantonese mode

---

## 🔍 Checking Current Language

### Method 1: Check Database

```bash
cd /home/raymok/projects/agents/6_mcp
uv run python -c "
from truthsocial_memory_db import *
import sqlite3
conn = sqlite3.connect('truthsocial_memory.db')
c = conn.cursor()
c.execute('SELECT output_content FROM ai_outputs WHERE ai_name=\"TradeEvaluator\" ORDER BY created_at DESC LIMIT 1')
text = c.fetchone()[0]
# Check if mostly Chinese
import re
chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
total = len(text.replace(' ', ''))
print(f'Chinese chars: {chinese}/{total} = {chinese/total*100:.1f}%')
print(f'Language: {"Cantonese" if chinese/total > 0.3 else "English"}')
"
```

### Method 2: Check Generated HTML

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader
grep -o "Best Buy\|最佳時機" index.html | head -1
# If shows "Best Buy" → English mode
# If shows "最佳時機" → Cantonese mode
```

---

## 🎯 Language in Different Components

| Component | English | Cantonese | Auto-Detected? |
|-----------|---------|-----------|----------------|
| AI Output | ✅ Set by .env | ✅ Set by .env | ❌ Manual setting |
| Website Labels | "Best Buy", "NIL" | "最佳時機", "無" | ✅ Auto from AI output |
| Stock Actions | BUY / SELL | 買入 (BUY) / 賣出 (SELL) | ✅ Auto from AI output |
| Section Headers | 📈📊🎯 (same) | 📈📊🎯 (same) | N/A |
| Analysis Text | English | Cantonese | From AI |

---

## 🆕 Adding New Language Labels

If you want to add more bilingual labels:

**1. Define in `generate_html.py`:**

```python
# Around line 430
best_buy_label = '最佳時機' if is_cantonese == 'zh' else 'Best Buy'
your_label = '中文' if is_cantonese == 'zh' else 'English'
```

**2. Use in HTML generation:**

```python
f'''<div>{your_label}</div>'''
```

---

## 📝 Summary

### ✅ What's Automatic:
- Language detection from AI output
- UI label switching
- Action button text formatting

### ⚙️ What You Control:
- AI output language (via `.env` file)
- When to regenerate website

### 🚫 What Doesn't Exist:
- Manual language toggle button
- Runtime language switching
- Per-user language preferences

**Philosophy:** One analysis = One language. Simple and consistent.

---

## 💡 Pro Tips

### Tip 1: Keep Language Consistent
Don't mix English and Cantonese posts in the same database. Decide on one language and stick to it.

### Tip 2: Regenerate After Language Change
Always run both steps after changing `.env`:
```bash
uv run truthsocial1.py  # New analysis in new language
cd AITrader && ./update.sh  # Regenerate website
```

### Tip 3: Test Both Languages
Generate one post in English, one in Cantonese to see how it looks:
```bash
# English test
echo "TRUTHSOCIAL_CANTONESE=false" > .env
uv run truthsocial1.py

# Cantonese test  
echo "TRUTHSOCIAL_CANTONESE=true" > .env
uv run truthsocial1.py

# Check website
cd AITrader && ./update.sh
```

---

## 🆘 Troubleshooting

**Q: Labels showing wrong language?**
A: Check if AI output is in expected language. Detection is based on content.

**Q: Mixed English/Chinese in same post?**
A: Detection uses 30% threshold. If >30% Chinese → Cantonese mode.

**Q: Want to force English mode?**
A: Modify detection threshold in `generate_html.py` line 271

**Q: How to add third language?**
A: Extend `detect_language()` function and add new label sets

---

**Version:** 2.2 - Language System
**Last Updated:** 2025-10-31
**Status:** ✅ Fully Automatic

