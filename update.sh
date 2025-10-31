#!/bin/bash
# Simple update script - regenerates HTML without git
# Use this if you just want to preview locally

set -e

echo "🔄 AI Trader - Update Website"
echo "=============================="

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📊 Regenerating HTML from database..."
uv run python generate_html.py

if [ ! -f "index.html" ]; then
    echo "❌ Error: index.html was not generated!"
    exit 1
fi

echo ""
echo "✅ Website updated successfully!"
echo ""
echo "📁 Files updated:"
echo "   - index.html ($(ls -lh index.html | awk '{print $5}'))"
echo ""
echo "🌐 To preview:"
echo "   1. Open index.html in your browser"
echo "   2. Or run: python -m http.server 8000"
echo "      Then visit: http://localhost:8000"
echo ""
echo "📤 To deploy to GitHub Pages:"
echo "   Run: ./deploy.sh"
echo ""
echo "=============================="

