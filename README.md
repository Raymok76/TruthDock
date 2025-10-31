# AI Trader Website

A static website that displays Truth Social post analyses from multi-agent AI trading advisors (OpenAI & DeepSeek).

## 📁 Project Structure

```
AITrader/
├── generate_html.py      # Main script to generate website from database
├── index.html           # Generated website (do not edit manually)
├── styles.css           # Responsive CSS styling
├── infinite-scroll.js   # Lazy loading implementation
├── assets/              # Static assets folder
│   ├── trump_icon.jpg   # Poster icon (you need to provide)
│   └── truth_logo.png   # Truth Social logo (you need to provide)
└── README.md           # This file
```

## 🚀 Quick Start

### 1. Generate Analyses (First Time)

Run the main analysis script to fetch and analyze Truth Social posts:

```bash
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py
```

This will:
- Fetch latest post from @realDonaldTrump
- Analyze with OpenAI advisor
- Analyze with DeepSeek advisor
- Synthesize with TradeEvaluator
- Save everything to `truthsocial_memory.db`

### 2. Generate Website

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader
uv run generate_html.py
```

This will:
- Read all analyses from database
- Parse AI outputs for stock/options picks
- Generate responsive HTML with lazy loading
- Output to `index.html`

### 3. Preview Locally

Open `index.html` in your browser:

```bash
# Linux
xdg-open index.html

# Or use Python HTTP server
python -m http.server 8000
# Then visit: http://localhost:8000
```

## 📸 Required Assets

You need to provide two image files in the `assets/` folder:

1. **trump_icon.jpg** - Donald Trump poster icon
   - Recommended size: 200x200px
   - Format: JPG or PNG
   - Used as poster avatar

2. **truth_logo.png** - Truth Social logo
   - Recommended size: 300x100px (wide)
   - Format: PNG with transparency
   - Used as branding header

If these files are missing, the website will still work but won't show the images.

## 🌐 Deploy to GitHub Pages

### Option A: Manual Deployment

1. Create a new GitHub repository (or use existing)

2. Initialize git (if not already):
```bash
cd /home/raymok/projects/agents/6_mcp/AITrader
git init
```

3. Add files and commit:
```bash
git add index.html styles.css infinite-scroll.js assets/
git commit -m "Initial AI Trader website"
```

4. Connect to GitHub:
```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

5. Enable GitHub Pages:
   - Go to repository Settings → Pages
   - Source: Deploy from branch
   - Branch: `main` / root
   - Save

6. Visit: `https://YOUR_USERNAME.github.io/YOUR_REPO/`

### Option B: Automated Deployment Script

Create a deployment script:

```bash
#!/bin/bash
# deploy.sh

cd /home/raymok/projects/agents/6_mcp

# Step 1: Run analysis (optional - only if you want fresh data)
# uv run truthsocial1.py

# Step 2: Generate HTML
cd AITrader
uv run generate_html.py

# Step 3: Deploy to GitHub
git add index.html
git commit -m "Update: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main

echo "✅ Deployed to GitHub Pages!"
```

Make it executable:
```bash
chmod +x deploy.sh
```

Run whenever you want to update:
```bash
./deploy.sh
```

## ⚙️ Configuration

Edit `generate_html.py` to customize:

```python
# How many posts per batch in lazy loading
POSTS_PER_BATCH = 5

# How many batches to show immediately
INITIAL_VISIBLE_BATCHES = 1  # Shows 5 posts

# Maximum posts on main page
MAX_POSTS_ON_MAIN_PAGE = 30
```

## 📱 Features

- ✅ **Responsive Design**: Works on desktop, tablet, and mobile
- ✅ **Infinite Scroll**: Lazy loading for smooth performance
- ✅ **Bilingual Support**: Handles both English and Cantonese outputs
- ✅ **Smart Parsing**: Extracts stock/options recommendations from AI text
- ✅ **Fast Loading**: Only loads initial 5 posts, rest on scroll
- ✅ **Static Site**: Perfect for GitHub Pages (no backend needed)
- ✅ **Graceful Degradation**: Works even without JavaScript

## 🔄 Workflow

### Regular Updates

When you have new Truth Social posts to analyze:

```bash
# 1. Run analysis
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py

# 2. Generate updated HTML
cd AITrader
uv run generate_html.py

# 3. Deploy (if using GitHub Pages)
git add index.html
git commit -m "Update $(date '+%Y-%m-%d')"
git push
```

### Automation with Cron

You can automate this with a cron job:

```bash
crontab -e
```

Add this line to run daily at 9 AM:
```
0 9 * * * cd /home/raymok/projects/agents/6_mcp && uv run truthsocial1.py && cd AITrader && uv run generate_html.py && git add index.html && git commit -m "Auto-update $(date)" && git push
```

## 🎨 Customization

### Styling

Edit `styles.css` to customize:
- Colors (CSS variables at top)
- Layout (grid/flexbox)
- Fonts
- Animations

### Layout

The website structure:
1. **Header**: Shows most recent stock/options picks
2. **Post Content**: Truth Social post text
3. **Analysis**: Full AI recommendation
4. **Lazy Loading**: Older posts load on scroll

### Language Detection

The system automatically detects if output is Cantonese:
- Uses "無" for empty recommendations in Chinese
- Uses "NIL" for empty recommendations in English

## 🐛 Troubleshooting

### No analyses showing

**Problem**: Website shows "No analyses available"

**Solution**: Run `truthsocial1.py` first to generate data

```bash
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py
```

### Images not showing

**Problem**: Broken image icons

**Solution**: Add image files to `assets/` folder:
- `trump_icon.jpg`
- `truth_logo.png`

### Database not found

**Problem**: Error: "Database not found: truthsocial_memory.db"

**Solution**: Database is in parent directory. Script handles this automatically, but make sure `truthsocial1.py` has run at least once.

### Parsing issues

**Problem**: Stock/options not detected correctly

**Solution**: The AI outputs are free-form text. If format changes, update regex patterns in `generate_html.py`:
- `parse_stock_picks()` function
- `parse_options_picks()` function

## 📊 Performance

Expected load times (4G connection):

| Posts | Initial Load | Total HTML Size |
|-------|-------------|-----------------|
| 10    | 0.5s        | ~500KB          |
| 30    | 1.5s        | ~1.5MB          |
| 50    | 2.5s        | ~2.5MB          |

With lazy loading:
- First 5 posts load immediately
- Additional posts load on scroll (instant, already in HTML)
- After 30 posts, consider archiving older posts

## 🔗 Related Files

- `../truthsocial1.py` - Main analysis script
- `../truthsocial_trader.py` - AI advisor implementations
- `../truthsocial_memory_db.py` - Database functions
- `../truthsocial_db.py` - Post tracking database

## 📝 License

Part of the AI Agents project.

## 🙋 Support

For issues or questions, refer to the main project documentation.

---

**Generated with ❤️ by AI Multi-Agent Trading System**

