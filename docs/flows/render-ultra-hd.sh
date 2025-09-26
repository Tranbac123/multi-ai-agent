#!/bin/bash

# 🎨 Ultra-High Resolution Mermaid Diagram Renderer
# This script renders all .mmd files in multiple high-resolution formats

set -e

echo "🎨 Starting Ultra-HD Mermaid diagram rendering..."

# Create output directories
mkdir -p docs/flows/rendered/4K
mkdir -p docs/flows/rendered/8K
mkdir -p docs/flows/rendered/SVG
mkdir -p docs/flows/rendered/PDF

# Theme and background
THEME="dark"
BACKGROUND="white"

# Function to render in multiple formats
render_ultra_hd() {
    local input_file="$1"
    local base_name="$2"
    local description="$3"
    
    echo "📊 Rendering: $description"
    echo "   Input:  $input_file"
    
    # 4K Resolution (3840x2160)
    echo "   🖼️  Rendering 4K (3840x2160)..."
    if mmdc -i "$input_file" -o "docs/flows/rendered/4K/${base_name}-4K.png" \
            -t "$THEME" -b "$BACKGROUND" -s 3 -w 3840 -H 2160; then
        echo "   ✅ 4K Success: ${base_name}-4K.png"
    else
        echo "   ❌ 4K Failed: ${base_name}-4K.png"
    fi
    
    # 8K Resolution (7680x4320) - for very large diagrams
    echo "   🖼️  Rendering 8K (7680x4320)..."
    if mmdc -i "$input_file" -o "docs/flows/rendered/8K/${base_name}-8K.png" \
            -t "$THEME" -b "$BACKGROUND" -s 6 -w 7680 -H 4320; then
        echo "   ✅ 8K Success: ${base_name}-8K.png"
    else
        echo "   ❌ 8K Failed: ${base_name}-8K.png"
    fi
    
    # SVG Format (vector, infinitely scalable)
    echo "   🎨 Rendering SVG (vector)..."
    if mmdc -i "$input_file" -o "docs/flows/rendered/SVG/${base_name}.svg" \
            -t "$THEME" -b "$BACKGROUND"; then
        echo "   ✅ SVG Success: ${base_name}.svg"
    else
        echo "   ❌ SVG Failed: ${base_name}.svg"
    fi
    
    # PDF Format (printable)
    echo "   📄 Rendering PDF (printable)..."
    if mmdc -i "$input_file" -o "docs/flows/rendered/PDF/${base_name}.pdf" \
            -t "$THEME" -b "$BACKGROUND" -s 2; then
        echo "   ✅ PDF Success: ${base_name}.pdf"
    else
        echo "   ❌ PDF Failed: ${base_name}.pdf"
    fi
    
    echo ""
}

# Render all diagrams in ultra-high resolution
echo "🔄 Rendering all diagrams in ultra-high resolution..."

render_ultra_hd "docs/flows/detailed-visual-flow.mmd" "detailed-visual-flow" "Detailed Visual System Map"
render_ultra_hd "docs/flows/detailed-sequence-flow.mmd" "detailed-sequence-flow" "Detailed Sequence Flow"
render_ultra_hd "docs/flows/comprehensive-data-flow.mmd" "comprehensive-data-flow" "Comprehensive Data Flow"
render_ultra_hd "docs/flows/complete-architecture-flow.mmd" "complete-architecture-flow" "Complete Architecture Flow"
render_ultra_hd "docs/flows/system-map.mmd" "system-map" "System Architecture Map"

render_ultra_hd "docs/flows/flow-web-chat.mmd" "flow-web-chat" "Web Chat Flow"
render_ultra_hd "docs/flows/flow-chat-adapters.mmd" "flow-chat-adapters" "Chat Adapters Flow"
render_ultra_hd "docs/flows/flow-ingestion.mmd" "flow-ingestion" "Document Ingestion Flow"
render_ultra_hd "docs/flows/flow-retrieval.mmd" "flow-retrieval" "Retrieval Flow"
render_ultra_hd "docs/flows/flow-billing-analytics.mmd" "flow-billing-analytics" "Billing & Analytics Flow"

echo "🎉 Ultra-HD rendering completed!"
echo ""
echo "📁 Generated files:"
echo "   🖼️  4K Images: docs/flows/rendered/4K/"
echo "   🖼️  8K Images: docs/flows/rendered/8K/"
echo "   🎨 SVG Files:  docs/flows/rendered/SVG/"
echo "   📄 PDF Files:  docs/flows/rendered/PDF/"
echo ""
echo "📊 File sizes:"
find docs/flows/rendered -name "*.png" -exec ls -lh {} \; | awk '{print "   📊 " $9 " (" $5 ")"}'
find docs/flows/rendered -name "*.svg" -exec ls -lh {} \; | awk '{print "   🎨 " $9 " (" $5 ")"}'
find docs/flows/rendered -name "*.pdf" -exec ls -lh {} \; | awk '{print "   📄 " $9 " (" $5 ")"}'
echo ""
echo "💡 Usage recommendations:"
echo "   🖼️  4K PNG: Best for presentations and documentation"
echo "   🖼️  8K PNG: Best for large displays and detailed analysis"
echo "   🎨 SVG: Best for web and scalable graphics"
echo "   📄 PDF: Best for printing and sharing"
echo ""
echo "🌐 Quick viewing:"
echo "   • Open PNG files in any image viewer"
echo "   • Open SVG files in web browser"
echo "   • Open PDF files in PDF viewer"
echo "   • Use VS Code with Mermaid extension for live preview"
