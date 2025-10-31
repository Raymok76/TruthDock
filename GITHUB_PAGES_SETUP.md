# GitHub Pages Setup Guide

Complete step-by-step guide to deploy your AI Trader website to GitHub Pages.

## Prerequisites

- GitHub account
- Git installed on your system
- AI Trader website already generated (`index.html` exists)

## Option 1: Quick Setup (New Repository)

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `ai-trader` (or any name you prefer)
3. Description: "AI Truth Social Stock Analysis Website"
4. Choose **Public** (required for free GitHub Pages)
5. **DO NOT** initialize with README, .gitignore, or license
6. Click "Create repository"

### Step 2: Initialize Local Git

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader

# Initialize git
git init

# Add all files
git add .

# First commit
git commit -m "Initial AI Trader website"

# Connect to GitHub (replace YOUR_USERNAME and YOUR_REPO)
git remote add origin https://github.com/YOUR_USERNAME/ai-trader.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 3: Enable GitHub Pages

1. Go to your repository: `https://github.com/YOUR_USERNAME/ai-trader`
2. Click **Settings** (top menu)
3. Scroll down to **Pages** (left sidebar)
4. Under "Source":
   - Select branch: `main`
   - Folder: `/ (root)`
5. Click **Save**
6. Wait 1-2 minutes for deployment

### Step 4: Visit Your Website

Your website will be available at:
```
https://YOUR_USERNAME.github.io/ai-trader/
```

🎉 **Done!** Your AI Trader website is now live!

---

## Option 2: Add to Existing Repository

If you already have a repository:

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader

# Clone your existing repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git temp_repo

# Copy AI Trader files into it
cp -r * temp_repo/
mv temp_repo ../AITrader_deploy
cd ../AITrader_deploy

# Commit and push
git add .
git commit -m "Add AI Trader website"
git push origin main
```

Then follow Step 3 above to enable GitHub Pages.

---

## Updating Your Website

### Automatic Update (Recommended)

Use the deployment script:

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader
./deploy.sh
```

This will:
1. Regenerate HTML from latest database
2. Commit changes
3. Push to GitHub
4. Automatically deploy to GitHub Pages

### Manual Update

```bash
cd /home/raymok/projects/agents/6_mcp/AITrader

# Regenerate HTML
uv run python generate_html.py

# Commit and push
git add index.html
git commit -m "Update analyses - $(date '+%Y-%m-%d')"
git push origin main
```

GitHub Pages will automatically rebuild within 1-2 minutes.

---

## Complete Workflow

### Daily/Regular Updates

```bash
# 1. Run Truth Social analysis
cd /home/raymok/projects/agents/6_mcp
uv run truthsocial1.py

# 2. Deploy updated website
cd AITrader
./deploy.sh
```

### Automated Workflow (Cron Job)

Run analysis and deploy daily at 9 AM:

```bash
crontab -e
```

Add this line:
```cron
0 9 * * * cd /home/raymok/projects/agents/6_mcp && uv run truthsocial1.py && cd AITrader && ./deploy.sh >> /tmp/aitrader-deploy.log 2>&1
```

---

## Troubleshooting

### 404 Error After Setup

**Problem**: Website shows 404 after enabling GitHub Pages

**Solutions**:
1. Wait 2-5 minutes (first deployment takes longer)
2. Make sure repository is **Public**
3. Check GitHub Pages settings (Settings → Pages)
4. Verify `index.html` is in the repository root
5. Clear browser cache and try again

### Images Not Showing

**Problem**: Broken image icons on website

**Solution**: Add image files to `assets/` folder:
```bash
cd /home/raymok/projects/agents/6_mcp/AITrader/assets
# Add your images:
# - trump_icon.jpg
# - truth_logo.png
```

Then commit and push:
```bash
git add assets/
git commit -m "Add image assets"
git push origin main
```

### Git Push Fails (Authentication)

**Problem**: Git push asks for password but password doesn't work

**Solution**: Use Personal Access Token (PAT):

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (full control)
4. Copy the token
5. When pushing, use token as password:
   ```
   Username: YOUR_USERNAME
   Password: ghp_xxxxxxxxxxxxxxxxxxxx (your token)
   ```

**Better Solution**: Configure Git credentials:
```bash
# Cache credentials for 1 hour
git config --global credential.helper 'cache --timeout=3600'

# Or store permanently (less secure)
git config --global credential.helper store
```

### Deploy Script Fails

**Problem**: `./deploy.sh` shows "Permission denied"

**Solution**:
```bash
chmod +x /home/raymok/projects/agents/6_mcp/AITrader/deploy.sh
```

### Website Not Updating

**Problem**: Pushed changes but website not updating

**Solutions**:
1. Check GitHub Actions tab (if using Actions)
2. Wait 2-3 minutes for GitHub Pages rebuild
3. Clear browser cache (Ctrl+Shift+R)
4. Check commit actually pushed: `git log origin/main`
5. Verify `index.html` was committed: `git show HEAD:index.html`

---

## Custom Domain (Optional)

Want to use your own domain like `aitrader.yourname.com`?

1. Add file `CNAME` to repository:
   ```bash
   echo "aitrader.yourname.com" > CNAME
   git add CNAME
   git commit -m "Add custom domain"
   git push
   ```

2. Configure DNS records at your domain provider:
   ```
   Type: CNAME
   Name: aitrader
   Value: YOUR_USERNAME.github.io
   ```

3. Wait for DNS propagation (5 minutes - 48 hours)

4. Enable HTTPS in GitHub Pages settings

---

## Security Considerations

### API Keys

**IMPORTANT**: This website is **static HTML only** - no API keys are included!

- The website only displays pre-generated analysis from the database
- It does NOT include:
  - OpenAI API keys
  - DeepSeek API keys
  - Truth Social credentials
  - Any sensitive data

All sensitive processing happens locally in `truthsocial1.py`, not in the website.

### Public Repository

- Your repository should be **Public** for free GitHub Pages
- Only commit the generated HTML, CSS, and JS
- **Never commit** `.env` files or credentials
- The `.gitignore` file prevents accidental commits

---

## Advanced: GitHub Actions (Optional)

Automate everything with GitHub Actions - regenerate HTML and deploy automatically when database updates.

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy AI Trader

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Generate HTML
        run: |
          pip install uv
          cd AITrader
          uv run python generate_html.py
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./AITrader
```

This runs automatically on every push to main branch.

---

## Support

For more help:
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Git Basics](https://git-scm.com/book/en/v2/Getting-Started-Git-Basics)
- Check main README.md in this folder

---

**Happy Deploying! 🚀**

