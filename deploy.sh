#!/bin/bash
# AI Trader Website Deployment Script
# This script regenerates the HTML and deploys to GitHub Pages

set -e  # Exit on error

echo "🚀 AI Trader Deployment Script"
echo "================================"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Step 1: Regenerate HTML from database
echo "📊 Step 1: Generating HTML from database..."
uv run python generate_html.py

if [ ! -f "index.html" ]; then
    echo "❌ Error: index.html was not generated!"
    exit 1
fi

echo "✅ HTML generated successfully"
echo ""

# Step 2: Check if git is initialized
if [ ! -d ".git" ]; then
    echo "⚠️  Git repository not initialized in AITrader folder"
    echo "   Please initialize git first:"
    echo "   git init"
    echo "   git remote add origin YOUR_GITHUB_REPO_URL"
    echo "   Then run this script again."
    exit 1
fi

# Step 3: Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "📝 Step 2: Committing changes..."
    
    # Stage all changes
    git add index.html styles.css infinite-scroll.js assets/ README.md
    
    # Create commit with timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    git commit -m "Update AI Trader website - $TIMESTAMP"
    
    echo "✅ Changes committed"
else
    echo "ℹ️  No changes to commit"
fi

echo ""

# Step 4: Push to GitHub
echo "🌐 Step 3: Pushing to GitHub..."

# Check if remote exists
if git remote get-url origin > /dev/null 2>&1; then
    git push origin main || git push origin master
    echo "✅ Pushed to GitHub successfully!"
    echo ""
    echo "🎉 Deployment complete!"
    echo "   Your website should be live at:"
    echo "   https://YOUR_USERNAME.github.io/YOUR_REPO/"
else
    echo "⚠️  No git remote configured"
    echo "   Please add a remote first:"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
    exit 1
fi

echo ""
echo "================================"

