#!/bin/bash

# 📸 High-Resolution Export Setup Script
# This script sets up comprehensive export tools for Mermaid diagrams

set -e

echo "📸 Setting up high-resolution export tools..."

# Create export directories
mkdir -p docs/flows/rendered/png/4K
mkdir -p docs/flows/rendered/png/8K
mkdir -p docs/flows/rendered/svg
mkdir -p docs/flows/rendered/pdf
mkdir -p docs/flows/rendered/jpg

# Create comprehensive export script
cat > docs/flows/export-all.sh << 'EOF'
#!/bin/bash

# 📸 Comprehensive Mermaid Export Tool
# Exports all diagrams in multiple formats and resolutions

set -e

echo "📸 Starting comprehensive diagram export..."

# Configuration
THEME="dark"
BACKGROUND="white"

# Export directories
PNG_4K_DIR="docs/flows/rendered/png/4K"
PNG_8K_DIR="docs/flows/rendered/png/8K"
SVG_DIR="docs/flows/rendered/svg"
PDF_DIR="docs/flows/rendered/pdf"
JPG_DIR="docs/flows/rendered/jpg"

# Function to export diagram in all formats
export_diagram() {
    local input_file="$1"
    local base_name="$2"
    local description="$3"
    
    echo "📊 Exporting: $description"
    echo "   Input: $input_file"
    
    # 4K PNG (3840x2160)
    echo "   🖼️  4K PNG..."
    if mmdc -i "$input_file" -o "$PNG_4K_DIR/${base_name}-4K.png" \
            -t "$THEME" -b "$BACKGROUND" -s 3 -w 3840 -H 2160; then
        echo "   ✅ 4K PNG: ${base_name}-4K.png"
    else
        echo "   ❌ 4K PNG failed"
    fi
    
    # 8K PNG (7680x4320)
    echo "   🖼️  8K PNG..."
    if mmdc -i "$input_file" -o "$PNG_8K_DIR/${base_name}-8K.png" \
            -t "$THEME" -b "$BACKGROUND" -s 6 -w 7680 -H 4320; then
        echo "   ✅ 8K PNG: ${base_name}-8K.png"
    else
        echo "   ❌ 8K PNG failed"
    fi
    
    # SVG (Vector)
    echo "   🎨 SVG..."
    if mmdc -i "$input_file" -o "$SVG_DIR/${base_name}.svg" \
            -t "$THEME" -b "$BACKGROUND"; then
        echo "   ✅ SVG: ${base_name}.svg"
    else
        echo "   ❌ SVG failed"
    fi
    
    # PDF (Print)
    echo "   📄 PDF..."
    if mmdc -i "$input_file" -o "$PDF_DIR/${base_name}.pdf" \
            -t "$THEME" -b "$BACKGROUND" -s 2; then
        echo "   ✅ PDF: ${base_name}.pdf"
    else
        echo "   ❌ PDF failed"
    fi
    
    # JPG (Compressed)
    echo "   📷 JPG..."
    if mmdc -i "$input_file" -o "$JPG_DIR/${base_name}.jpg" \
            -t "$THEME" -b "$BACKGROUND" -s 2 -w 1920 -H 1080; then
        echo "   ✅ JPG: ${base_name}.jpg"
    else
        echo "   ❌ JPG failed"
    fi
    
    echo ""
}

# Export all diagrams
echo "🔄 Exporting all diagrams..."

export_diagram "docs/flows/detailed-visual-flow.mmd" "detailed-visual-flow" "Detailed Visual System Map"
export_diagram "docs/flows/detailed-sequence-flow.mmd" "detailed-sequence-flow" "Detailed Sequence Flow"
export_diagram "docs/flows/comprehensive-data-flow.mmd" "comprehensive-data-flow" "Comprehensive Data Flow"
export_diagram "docs/flows/complete-architecture-flow.mmd" "complete-architecture-flow" "Complete Architecture Flow"
export_diagram "docs/flows/system-map.mmd" "system-map" "System Architecture Map"

export_diagram "docs/flows/flow-web-chat.mmd" "flow-web-chat" "Web Chat Flow"
export_diagram "docs/flows/flow-chat-adapters.mmd" "flow-chat-adapters" "Chat Adapters Flow"
export_diagram "docs/flows/flow-ingestion.mmd" "flow-ingestion" "Document Ingestion Flow"
export_diagram "docs/flows/flow-retrieval.mmd" "flow-retrieval" "Retrieval Flow"
export_diagram "docs/flows/flow-billing-analytics.mmd" "flow-billing-analytics" "Billing & Analytics Flow"

# Export from Markdown file
echo "📝 Exporting from Markdown file..."
if mmdc -i "docs/flows/SERVICE_FLOWS.md" -o "docs/flows/rendered/SERVICE_FLOWS" \
        -t "$THEME" -b "$BACKGROUND" -s 3 -w 4000 -H 3000; then
    echo "✅ Markdown export: SERVICE_FLOWS-*.png"
else
    echo "❌ Markdown export failed"
fi

echo "🎉 Export completed!"
echo ""
echo "📁 Generated files:"
echo "   🖼️  4K PNG: $PNG_4K_DIR/"
echo "   🖼️  8K PNG: $PNG_8K_DIR/"
echo "   🎨 SVG: $SVG_DIR/"
echo "   📄 PDF: $PDF_DIR/"
echo "   📷 JPG: $JPG_DIR/"
echo ""
echo "📊 File sizes:"
find docs/flows/rendered -name "*.png" -exec ls -lh {} \; | head -5 | awk '{print "   📊 " $9 " (" $5 ")"}'
find docs/flows/rendered -name "*.svg" -exec ls -lh {} \; | head -5 | awk '{print "   🎨 " $9 " (" $5 ")"}'
find docs/flows/rendered -name "*.pdf" -exec ls -lh {} \; | head -5 | awk '{print "   📄 " $9 " (" $5 ")"}'
echo ""
echo "💡 Usage recommendations:"
echo "   🖼️  4K PNG: Best for presentations and documentation"
echo "   🖼️  8K PNG: Best for large displays and detailed analysis"
echo "   🎨 SVG: Best for web and scalable graphics"
echo "   📄 PDF: Best for printing and sharing"
echo "   📷 JPG: Best for web and compressed storage"
EOF

chmod +x docs/flows/export-all.sh

# Create theme-specific export script
cat > docs/flows/export-themes.sh << 'EOF'
#!/bin/bash

# 🎨 Theme-Specific Export Script
# Exports diagrams in different themes for comparison

set -e

echo "🎨 Starting theme-specific export..."

# Themes to export
THEMES=("default" "dark" "forest" "neutral" "base")

# Create theme directories
for theme in "${THEMES[@]}"; do
    mkdir -p "docs/flows/rendered/themes/$theme"
done

# Function to export diagram in specific theme
export_theme() {
    local input_file="$1"
    local base_name="$2"
    local theme="$3"
    
    echo "🎨 Exporting $base_name in $theme theme..."
    
    if mmdc -i "$input_file" -o "docs/flows/rendered/themes/$theme/${base_name}-${theme}.png" \
            -t "$theme" -b "white" -s 3 -w 4000 -H 3000; then
        echo "   ✅ $theme: ${base_name}-${theme}.png"
    else
        echo "   ❌ $theme failed"
    fi
}

# Export all diagrams in all themes
for theme in "${THEMES[@]}"; do
    echo "🔄 Exporting in $theme theme..."
    
    export_theme "docs/flows/detailed-visual-flow.mmd" "detailed-visual-flow" "$theme"
    export_theme "docs/flows/detailed-sequence-flow.mmd" "detailed-sequence-flow" "$theme"
    export_theme "docs/flows/comprehensive-data-flow.mmd" "comprehensive-data-flow" "$theme"
    
    echo ""
done

echo "🎉 Theme export completed!"
echo ""
echo "📁 Generated files in docs/flows/rendered/themes/:"
for theme in "${THEMES[@]}"; do
    echo "   🎨 $theme/: $(ls docs/flows/rendered/themes/$theme/ | wc -l) files"
done
EOF

chmod +x docs/flows/export-themes.sh

# Create batch export script
cat > docs/flows/export-batch.sh << 'EOF'
#!/bin/bash

# 📦 Batch Export Script
# Exports specific diagrams or all diagrams based on arguments

set -e

# Default settings
THEME="dark"
BACKGROUND="white"
FORMAT="png"
RESOLUTION="4K"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --theme)
            THEME="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --resolution)
            RESOLUTION="$2"
            shift 2
            ;;
        --diagram)
            DIAGRAM="$2"
            shift 2
            ;;
        --help)
            echo "📦 Batch Export Script"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --theme <theme>       Theme (default, dark, forest, neutral, base)"
            echo "  --format <format>     Format (png, svg, pdf, jpg)"
            echo "  --resolution <res>    Resolution (4K, 8K, HD)"
            echo "  --diagram <name>      Specific diagram name"
            echo "  --help               Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Export all in 4K PNG"
            echo "  $0 --theme forest --format svg        # Export all in forest theme SVG"
            echo "  $0 --diagram detailed-visual-flow     # Export specific diagram"
            echo "  $0 --resolution 8K --format pdf       # Export all in 8K PDF"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "📦 Starting batch export..."
echo "   Theme: $THEME"
echo "   Format: $FORMAT"
echo "   Resolution: $RESOLUTION"

# Set resolution parameters
case $RESOLUTION in
    "4K")
        WIDTH=3840
        HEIGHT=2160
        SCALE=3
        ;;
    "8K")
        WIDTH=7680
        HEIGHT=4320
        SCALE=6
        ;;
    "HD")
        WIDTH=1920
        HEIGHT=1080
        SCALE=2
        ;;
    *)
        echo "❌ Invalid resolution: $RESOLUTION"
        echo "Valid resolutions: 4K, 8K, HD"
        exit 1
        ;;
esac

# Create output directory
OUTPUT_DIR="docs/flows/rendered/batch/$THEME-$FORMAT-$RESOLUTION"
mkdir -p "$OUTPUT_DIR"

# Function to export diagram
export_diagram() {
    local input_file="$1"
    local base_name="$2"
    local description="$3"
    
    echo "📊 Exporting: $description"
    
    if mmdc -i "$input_file" -o "$OUTPUT_DIR/${base_name}.$FORMAT" \
            -t "$THEME" -b "$BACKGROUND" -s $SCALE -w $WIDTH -H $HEIGHT; then
        echo "   ✅ ${base_name}.$FORMAT"
    else
        echo "   ❌ ${base_name}.$FORMAT failed"
    fi
}

# Export diagrams
if [ -n "$DIAGRAM" ]; then
    # Export specific diagram
    case $DIAGRAM in
        "detailed-visual-flow")
            export_diagram "docs/flows/detailed-visual-flow.mmd" "detailed-visual-flow" "Detailed Visual System Map"
            ;;
        "detailed-sequence-flow")
            export_diagram "docs/flows/detailed-sequence-flow.mmd" "detailed-sequence-flow" "Detailed Sequence Flow"
            ;;
        "comprehensive-data-flow")
            export_diagram "docs/flows/comprehensive-data-flow.mmd" "comprehensive-data-flow" "Comprehensive Data Flow"
            ;;
        *)
            echo "❌ Unknown diagram: $DIAGRAM"
            echo "Available diagrams: detailed-visual-flow, detailed-sequence-flow, comprehensive-data-flow"
            exit 1
            ;;
    esac
else
    # Export all diagrams
    export_diagram "docs/flows/detailed-visual-flow.mmd" "detailed-visual-flow" "Detailed Visual System Map"
    export_diagram "docs/flows/detailed-sequence-flow.mmd" "detailed-sequence-flow" "Detailed Sequence Flow"
    export_diagram "docs/flows/comprehensive-data-flow.mmd" "comprehensive-data-flow" "Comprehensive Data Flow"
    export_diagram "docs/flows/complete-architecture-flow.mmd" "complete-architecture-flow" "Complete Architecture Flow"
    export_diagram "docs/flows/system-map.mmd" "system-map" "System Architecture Map"
fi

echo "🎉 Batch export completed!"
echo "📁 Output directory: $OUTPUT_DIR"
echo "📊 Generated files:"
ls -la "$OUTPUT_DIR"/*.$FORMAT | awk '{print "   📊 " $9 " (" $5 ")"}'
EOF

chmod +x docs/flows/export-batch.sh

# Create export dashboard
cat > docs/flows/export-dashboard.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-AI-Agent Platform - Export Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
        }
        .export-section {
            margin-bottom: 40px;
            padding: 20px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #fafafa;
        }
        .export-title {
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
        }
        .export-description {
            color: #666;
            margin-bottom: 20px;
        }
        .export-commands {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
            font-family: 'Courier New', monospace;
            margin: 10px 0;
        }
        .export-btn {
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 5px;
            font-size: 0.9em;
        }
        .export-btn:hover {
            background: #0056b3;
        }
        .format-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .format-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
            text-align: center;
        }
        .format-title {
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .format-description {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }
        .resolution-selector {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 10px;
            margin: 15px 0;
        }
        .resolution-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.8em;
        }
        .resolution-btn:hover {
            background: #218838;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📸 Multi-AI-Agent Platform - Export Dashboard</h1>
        
        <div class="export-section">
            <div class="export-title">🚀 Quick Export</div>
            <div class="export-description">Export all diagrams in high resolution with one command</div>
            <div class="export-commands">
                ./docs/flows/export-all.sh
            </div>
            <a href="#" class="export-btn" onclick="runExport('all')">📸 Export All</a>
        </div>
        
        <div class="export-section">
            <div class="export-title">🎨 Theme Export</div>
            <div class="export-description">Export diagrams in different themes for comparison</div>
            <div class="export-commands">
                ./docs/flows/export-themes.sh
            </div>
            <a href="#" class="export-btn" onclick="runExport('themes')">🎨 Export Themes</a>
        </div>
        
        <div class="export-section">
            <div class="export-title">📦 Batch Export</div>
            <div class="export-description">Export with custom parameters</div>
            <div class="export-commands">
                ./docs/flows/export-batch.sh --theme dark --format png --resolution 4K
            </div>
            <a href="#" class="export-btn" onclick="runExport('batch')">📦 Batch Export</a>
        </div>
        
        <div class="export-section">
            <div class="export-title">📊 Export Formats</div>
            <div class="export-description">Choose the best format for your needs</div>
            
            <div class="format-grid">
                <div class="format-card">
                    <div class="format-title">🖼️ PNG</div>
                    <div class="format-description">Best for presentations and documentation</div>
                    <div class="resolution-selector">
                        <button class="resolution-btn" onclick="exportFormat('png', '4K')">4K</button>
                        <button class="resolution-btn" onclick="exportFormat('png', '8K')">8K</button>
                        <button class="resolution-btn" onclick="exportFormat('png', 'HD')">HD</button>
                    </div>
                </div>
                
                <div class="format-card">
                    <div class="format-title">🎨 SVG</div>
                    <div class="format-description">Best for web and scalable graphics</div>
                    <button class="resolution-btn" onclick="exportFormat('svg', 'vector')" style="width: 100%;">Vector</button>
                </div>
                
                <div class="format-card">
                    <div class="format-title">📄 PDF</div>
                    <div class="format-description">Best for printing and sharing</div>
                    <button class="resolution-btn" onclick="exportFormat('pdf', 'print')" style="width: 100%;">Print</button>
                </div>
                
                <div class="format-card">
                    <div class="format-title">📷 JPG</div>
                    <div class="format-description">Best for web and compressed storage</div>
                    <button class="resolution-btn" onclick="exportFormat('jpg', 'compressed')" style="width: 100%;">Compressed</button>
                </div>
            </div>
        </div>
        
        <div class="export-section">
            <div class="export-title">📁 Output Directories</div>
            <div class="export-description">Generated files are organized in these directories:</div>
            <div class="export-commands">
                docs/flows/rendered/png/4K/     # 4K PNG files
                docs/flows/rendered/png/8K/     # 8K PNG files
                docs/flows/rendered/svg/        # SVG files
                docs/flows/rendered/pdf/        # PDF files
                docs/flows/rendered/jpg/        # JPG files
                docs/flows/rendered/themes/     # Theme variations
                docs/flows/rendered/batch/      # Batch exports
            </div>
        </div>
    </div>
    
    <script>
        function runExport(type) {
            alert(`Running ${type} export...\nCheck the terminal for progress.`);
        }
        
        function exportFormat(format, resolution) {
            alert(`Exporting in ${format} format at ${resolution} resolution...\nCheck the terminal for progress.`);
        }
    </script>
</body>
</html>
EOF

echo "✅ High-resolution export setup complete!"
echo ""
echo "📁 Created export tools:"
echo "   • export-all.sh - Comprehensive export in all formats"
echo "   • export-themes.sh - Export in different themes"
echo "   • export-batch.sh - Custom parameter export"
echo "   • export-dashboard.html - Web dashboard for export tools"
echo ""
echo "🚀 How to use:"
echo "   1. Quick export: ./docs/flows/export-all.sh"
echo "   2. Theme export: ./docs/flows/export-themes.sh"
echo "   3. Custom export: ./docs/flows/export-batch.sh --theme dark --format png --resolution 4K"
echo "   4. Web dashboard: open docs/flows/export-dashboard.html"
echo ""
echo "📊 Export formats available:"
echo "   • PNG: 4K (3840x2160), 8K (7680x4320), HD (1920x1080)"
echo "   • SVG: Vector format, infinitely scalable"
echo "   • PDF: Print-ready format"
echo "   • JPG: Compressed format for web"
echo ""
echo "🎨 Themes available:"
echo "   • default, dark, forest, neutral, base"
