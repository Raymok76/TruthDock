#!/bin/bash
# AI Trader Website Deployment Script
# This script regenerates the HTML and deploys to GitHub Pages

set -e  # Exit on error

echo "🚀 AI Trader Deployment Script"
echo "================================"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Parse arguments
TRIGGER_VOTES=0
for arg in "$@"; do
    case "$arg" in
        --trigger-votes)
            TRIGGER_VOTES=1
            shift
            ;;
        *)
            ;;
    esac
done

# Step 1: Regenerate HTML from database
echo "📊 Step 1: Generating HTML from database..."
uv run python python/generate_html.py

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

# Step 3: Ensure GitHub Actions workflow exists (for vote processing)
if [ ! -f ".github/workflows/process-votes.yml" ]; then
    echo "🧩 Setting up GitHub Actions workflow for vote processing..."
    mkdir -p .github/workflows
    cat > .github/workflows/process-votes.yml << 'EOF'
name: Process Votes and Regenerate HTML

on:
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:
  push:
    paths:
      - 'votes/pending_votes.json'

jobs:
  process-votes:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Install dependencies
        run: |
          uv pip install --system -r requirements.txt || true
          uv pip install --system python-dotenv || true
      - name: Sync votes from SQLite to JSON
        run: |
          cd python
          uv run sync_votes.py || echo "No SQLite votes to sync"
      - name: Process pending votes
        run: |
          cd python
          uv run process_votes.py
      - name: Commit and push changes
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add votes/votes.json index.html
          git diff --staged --quiet || git commit -m "Auto-update: Process votes and regenerate HTML [skip ci]"
          git push
EOF
fi

# Step 4: Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "📝 Step 2: Committing changes..."
    
    # Stage only necessary site and workflow files
    git add index.html styles.css infinite-scroll.js timeline-indicator.js assets/ votes/votes.json
    # Optionally include pending votes to trigger workflow on push
    if [ "$TRIGGER_VOTES" -eq 1 ] && [ -f "votes/pending_votes.json" ]; then
        git add votes/pending_votes.json
        echo "🔔 Including votes/pending_votes.json to trigger workflow"
    fi
    [ -f ".github/workflows/process-votes.yml" ] && git add .github/workflows/process-votes.yml
    [ -f "requirements.txt" ] && git add requirements.txt
    
    # Create commit with timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    git commit -m "Update AI Trader website - $TIMESTAMP"
    
    echo "✅ Changes committed"
else
    echo "ℹ️  No changes to commit"
fi

echo ""

# Step 5: Push to GitHub
echo "🌐 Step 3: Pushing to GitHub..."

# Check if remote exists
if git remote get-url origin > /dev/null 2>&1; then
    # Determine current branch name
    CURRENT_BRANCH=$(git branch --show-current)
    
    if [ -z "$CURRENT_BRANCH" ]; then
        # No branch checked out, try to determine from remote
        echo "⚠️  No branch checked out. Checking remote branches..."
        REMOTE_BRANCH=$(git ls-remote --heads origin | head -1 | sed 's/.*refs\/heads\///')
        if [ -n "$REMOTE_BRANCH" ]; then
            echo "   Found remote branch: $REMOTE_BRANCH"
            git checkout -b "$REMOTE_BRANCH" || git checkout "$REMOTE_BRANCH"
            CURRENT_BRANCH="$REMOTE_BRANCH"
        else
            # Default to main
            CURRENT_BRANCH="main"
            git checkout -b main 2>/dev/null || true
        fi
    fi
    
    echo "📥 Pulling latest changes from remote..."
    # Pull with rebase to avoid merge commits, or merge if rebase fails
    git pull origin "$CURRENT_BRANCH" --rebase || git pull origin "$CURRENT_BRANCH" || {
        echo "⚠️  Pull failed. You may have local changes that conflict."
        echo "   Please resolve conflicts manually and run the script again."
        exit 1
    }
    
    echo "📤 Pushing to GitHub..."
    git push origin "$CURRENT_BRANCH"
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

