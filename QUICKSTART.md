# AI Trader Website - Quick Start

Get your AI Trader website running in 3 minutes!

## 🚀 Super Quick Start

### Step 1: Generate Website

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader
uv run python generate_html.py
```

### Step 2: Preview

Open `index.html` in your browser or:

```bash
python -m http.server 8000
# Visit: http://localhost:8000
```

**That's it!** Your website is ready to view locally.

---

## 📤 Deploy to GitHub Pages (Optional)

### One-Time Setup

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader

# 1. Initialize git
git init

# 2. Connect to GitHub (create repo first at github.com)
git remote add origin https://github.com/YOUR_USERNAME/ai-trader.git

# 3. Initial commit and push
git add .
git commit -m "Initial AI Trader website"
git branch -M main
git push -u origin main
```

### Enable GitHub Pages

1. Go to your repo settings: `https://github.com/YOUR_USERNAME/ai-trader/settings/pages`
2. Source: `main` branch, `/ (root)` folder
3. Save
4. Visit: `https://YOUR_USERNAME.github.io/ai-trader/`

### Future Updates

Just run:
```bash
./deploy.sh
```

---

## 🔄 Regular Workflow

### When New Truth Social Post Available

```bash
# 1. Analyze post (run from parent directory)
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py

# 2. Update website
cd AITrader
./update.sh

# 3. (Optional) Deploy to GitHub Pages
./deploy.sh
```

---

## 📁 Project Structure

```
AITrader/
├── generate_html.py        # Main generator script
├── index.html             # Generated website
├── styles.css             # Styling
├── infinite-scroll.js     # Lazy loading
├── assets/
│   ├── trump_icon.jpg     # (you need to add)
│   └── truth_logo.png     # (you need to add)
├── update.sh              # Quick regenerate script
├── deploy.sh              # Deploy to GitHub Pages
├── README.md              # Full documentation
├── GITHUB_PAGES_SETUP.md  # Detailed GitHub setup
└── QUICKSTART.md          # This file
```

---

## 📸 Add Images (Optional)

To show images on the website, add these files to `assets/` folder:

1. **trump_icon.jpg** - Trump profile picture (200x200px)
2. **truth_logo.png** - Truth Social logo (300x100px)

Without these files, the website still works but won't display the images.

---

## ⚙️ Customization

### Change Number of Posts Displayed

Edit `generate_html.py`:

```python
MAX_POSTS_ON_MAIN_PAGE = 30  # Change to any number
POSTS_PER_BATCH = 5          # Posts per lazy-load batch
```

### Change Styling

Edit `styles.css` - all colors are in CSS variables at the top:

```css
:root {
    --primary-color: #4169E1;  /* Change colors here */
    --header-bg: #D3D3D3;
    /* ... */
}
```

---

## 🐛 Common Issues

**Q: No analyses showing on website?**

A: Run `truthsocial1.py` first to generate analyses in the database.

**Q: Images not showing?**

A: Add image files to `assets/` folder (optional).

**Q: Website not updating on GitHub Pages?**

A: Wait 2-3 minutes after pushing, then clear browser cache (Ctrl+Shift+R).

---

## 📚 More Help

- **Full Documentation**: See `README.md`
- **GitHub Pages Setup**: See `GITHUB_PAGES_SETUP.md`
- **Main Project**: See `../truthsocial1.py`

---

**Happy Trading! 📈**

