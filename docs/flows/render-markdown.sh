#!/bin/bash

# 🎨 Markdown Mermaid Diagram Renderer
# This script renders Mermaid diagrams from Markdown files

set -e

echo "🎨 Starting Markdown Mermaid rendering..."

# Create output directory
mkdir -p docs/flows/rendered/markdown

# Theme and background
THEME="dark"
BACKGROUND="white"

# Function to render Markdown file
render_markdown() {
    local input_file="$1"
    local output_prefix="$2"
    local description="$3"
    
    echo "📊 Rendering: $description"
    echo "   Input:  $input_file"
    
    # Render all diagrams from Markdown
    if mmdc -i "$input_file" -o "docs/flows/rendered/markdown/${output_prefix}" \
            -t "$THEME" -b "$BACKGROUND" -s 3 -w 4000 -H 3000; then
        echo "   ✅ Success: ${output_prefix}*"
    else
        echo "   ❌ Failed: ${output_prefix}"
    fi
    echo ""
}

# Render the main service flows document
render_markdown "docs/flows/SERVICE_FLOWS.md" "service-flows" "Complete Service Flows Document"

echo "🎉 Markdown rendering completed!"
echo ""
echo "📁 Generated files in: docs/flows/rendered/markdown/"
echo ""
echo "📋 Rendered diagrams:"
ls -la docs/flows/rendered/markdown/*.png | awk '{print "   📊 " $9 " (" $5 " bytes)"}'
echo ""
echo "💡 Usage:"
echo "   • Open PNG files in any image viewer"
echo "   • Use VS Code with Mermaid extension for live preview"
echo "   • View original .md file in GitHub for interactive diagrams"
echo ""
echo "🌐 Quick viewing:"
echo "   • VS Code: code docs/flows/SERVICE_FLOWS.md"
echo "   • GitHub: Push to repository and view online"
echo "   • Mermaid Live: Copy diagram code blocks"
