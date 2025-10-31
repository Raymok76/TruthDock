# Truth Dock Website

A static website that displays Truth Social post analysis.

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
python3 truthsocial1.py
or
uv run truthsocial1.py
```
**remember to add login and pw into your own .env file

This will:
- Fetch latest post from @realDonaldTrump
- Analyze with OpenAI advisor
- Analyze with DeepSeek advisor
- Synthesize with TradeEvaluator
- Save everything to `truthsocial_memory.db`

### 2. Generate Website

```bash
python3 run generate_html.py
or
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

## 🌐 Deploy to GitHub Pages

### Option A: Manual Deployment

1. Create a new GitHub repository (or use existing)

2. Initialize git (if not already):
```bash
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

## 🔄 Workflow

### Regular Updates

When you have new Truth Social posts to analyze:

```bash
# 1. Run analysis
python3 truthsocial1.py
or
uv run truthsocial1.py

# 2. Generate updated HTML
python3 generate_html.py
or
uv run generate_html.py

# 3. Deploy (if using GitHub Pages)
git add index.html
git commit -m "Update $(date '+%Y-%m-%d')"
git push
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

