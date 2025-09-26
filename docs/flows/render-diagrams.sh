#!/bin/bash

# 🎨 Mermaid Diagram Renderer Script
# This script renders all .mmd files to PNG images

set -e

echo "🎨 Starting Mermaid diagram rendering..."

# Create output directory if it doesn't exist
mkdir -p docs/flows/rendered

# Color scheme and theme
THEME="dark"
BACKGROUND="white"

# Function to render a diagram
render_diagram() {
    local input_file="$1"
    local output_file="$2"
    local description="$3"
    
    echo "📊 Rendering: $description"
    echo "   Input:  $input_file"
    echo "   Output: $output_file"
    
    if mmdc -i "$input_file" -o "$output_file" -t "$THEME" -b "$BACKGROUND"; then
        echo "   ✅ Success: $output_file"
    else
        echo "   ❌ Failed: $output_file"
        return 1
    fi
    echo ""
}

# Render all Mermaid diagrams
echo "🔄 Rendering Mermaid diagrams..."

render_diagram "docs/flows/system-map.mmd" "docs/flows/rendered/system-map.png" "System Architecture Map"
render_diagram "docs/flows/detailed-visual-flow.mmd" "docs/flows/rendered/detailed-visual-flow.png" "Detailed Visual System Map"
render_diagram "docs/flows/detailed-sequence-flow.mmd" "docs/flows/rendered/detailed-sequence-flow.png" "Detailed Sequence Flow"
render_diagram "docs/flows/comprehensive-data-flow.mmd" "docs/flows/rendered/comprehensive-data-flow.png" "Comprehensive Data Flow"
render_diagram "docs/flows/complete-architecture-flow.mmd" "docs/flows/rendered/complete-architecture-flow.png" "Complete Architecture Flow"

render_diagram "docs/flows/flow-web-chat.mmd" "docs/flows/rendered/flow-web-chat.png" "Web Chat Flow"
render_diagram "docs/flows/flow-chat-adapters.mmd" "docs/flows/rendered/flow-chat-adapters.png" "Chat Adapters Flow"
render_diagram "docs/flows/flow-ingestion.mmd" "docs/flows/rendered/flow-ingestion.png" "Document Ingestion Flow"
render_diagram "docs/flows/flow-retrieval.mmd" "docs/flows/rendered/flow-retrieval.png" "Retrieval Flow"
render_diagram "docs/flows/flow-billing-analytics.mmd" "docs/flows/rendered/flow-billing-analytics.png" "Billing & Analytics Flow"

echo "🎉 All Mermaid diagrams rendered successfully!"
echo ""
echo "📁 Generated images in: docs/flows/rendered/"
echo ""
echo "📋 Rendered diagrams:"
ls -la docs/flows/rendered/*.png | awk '{print "   📊 " $9 " (" $5 " bytes)"}'
echo ""
echo "🌐 To view the diagrams:"
echo "   1. Open the PNG files in any image viewer"
echo "   2. Use VS Code with Mermaid extension for live preview"
echo "   3. View in web browser using Mermaid Live Editor"
echo ""
echo "💡 Tips:"
echo "   - PNG files are optimized for presentations and documentation"
echo "   - Use 'mmdc -h' to see all available rendering options"
echo "   - Try different themes: dark, forest, neutral, base"
echo "   - Add '-s 2' for higher resolution (2x scaling)"
