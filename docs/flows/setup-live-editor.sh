#!/bin/bash

# 🌐 Mermaid Live Editor Setup Script
# This script creates tools for easy integration with Mermaid Live Editor

set -e

echo "🌐 Setting up Mermaid Live Editor integration..."

# Create directory for Live Editor files
mkdir -p docs/flows/live-editor

# Extract individual diagrams for Live Editor
echo "📊 Extracting individual diagrams for Live Editor..."

# Function to extract diagram
extract_diagram() {
    local input_file="$1"
    local diagram_name="$2"
    local start_marker="$3"
    local end_marker="$4"
    
    echo "📝 Extracting $diagram_name..."
    
    # Extract diagram content
    awk "/$start_marker/,/$end_marker/" "$input_file" | \
    sed '1d;$d' > "docs/flows/live-editor/${diagram_name}.mmd"
    
    # Create HTML wrapper for Live Editor
    cat > "docs/flows/live-editor/${diagram_name}.html" << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$diagram_name - Mermaid Live Editor</title>
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
        .editor-link {
            display: inline-block;
            background: #ff6b6b;
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 0;
            font-weight: bold;
            text-align: center;
            width: 100%;
            box-sizing: border-box;
        }
        .editor-link:hover {
            background: #ff5252;
        }
        .diagram-content {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
            margin: 20px 0;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            overflow-x: auto;
        }
        .instructions {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #2196f3;
            margin: 20px 0;
        }
        .copy-btn {
            background: #4caf50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 0;
        }
        .copy-btn:hover {
            background: #45a049;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 $diagram_name</h1>
        
        <div class="instructions">
            <h3>📋 How to use with Mermaid Live Editor:</h3>
            <ol>
                <li>Click the "Open in Mermaid Live Editor" button below</li>
                <li>Or copy the diagram code and paste it into <a href="https://mermaid.live/" target="_blank">Mermaid Live Editor</a></li>
                <li>Customize themes, colors, and styling</li>
                <li>Export as PNG, SVG, or PDF</li>
                <li>Share with team members</li>
            </ol>
        </div>
        
        <a href="https://mermaid.live/" target="_blank" class="editor-link">
            🌐 Open in Mermaid Live Editor
        </a>
        
        <h3>📝 Diagram Code:</h3>
        <div class="diagram-content" id="diagram-code">$(cat "docs/flows/live-editor/${diagram_name}.mmd")</div>
        
        <button class="copy-btn" onclick="copyToClipboard()">📋 Copy to Clipboard</button>
        
        <div class="instructions">
            <h3>💡 Pro Tips:</h3>
            <ul>
                <li>Use different themes (dark, forest, neutral, base)</li>
                <li>Export in high resolution for presentations</li>
                <li>Share links with team members</li>
                <li>Use SVG format for scalable graphics</li>
                <li>Try different color schemes</li>
            </ul>
        </div>
    </div>
    
    <script>
        function copyToClipboard() {
            const text = document.getElementById('diagram-code').textContent;
            navigator.clipboard.writeText(text).then(function() {
                alert('Diagram code copied to clipboard!');
            });
        }
    </script>
</body>
</html>
EOF
}

# Extract all diagrams from SERVICE_FLOWS.md
extract_diagram "SERVICE_FLOWS.md" "01-system-architecture" "## 🏗️ Complete System Architecture" "## 🔄 Complete User Journey"
extract_diagram "SERVICE_FLOWS.md" "02-user-journey" "## 🔄 Complete User Journey" "## 📊 Comprehensive Data Flow"
extract_diagram "SERVICE_FLOWS.md" "03-data-flow" "## 📊 Comprehensive Data Flow" "## 💬 Web Chat Flow"
extract_diagram "SERVICE_FLOWS.md" "04-web-chat" "## 💬 Web Chat Flow" "## 📱 Chat Adapters Flow"
extract_diagram "SERVICE_FLOWS.md" "05-chat-adapters" "## 📱 Chat Adapters Flow" "## 📥 Document Ingestion Flow"
extract_diagram "SERVICE_FLOWS.md" "06-document-ingestion" "## 📥 Document Ingestion Flow" "## 🔍 Retrieval Flow"
extract_diagram "SERVICE_FLOWS.md" "07-retrieval" "## 🔍 Retrieval Flow" "## 📊 Billing & Analytics Flow"
extract_diagram "SERVICE_FLOWS.md" "08-billing-analytics" "## 📊 Billing & Analytics Flow" "---"

# Create main index page
cat > docs/flows/live-editor/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-AI-Agent Platform - Mermaid Live Editor</title>
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
        .diagram-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .diagram-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #e9ecef;
            text-align: center;
            transition: transform 0.2s;
        }
        .diagram-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .diagram-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
        }
        .diagram-description {
            color: #666;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        .view-btn {
            display: inline-block;
            background: #ff6b6b;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 5px;
            font-size: 0.9em;
        }
        .view-btn:hover {
            background: #ff5252;
        }
        .live-editor-btn {
            background: #4caf50;
        }
        .live-editor-btn:hover {
            background: #45a049;
        }
        .instructions {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #2196f3;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 Multi-AI-Agent Platform - Mermaid Live Editor</h1>
        
        <div class="instructions">
            <h3>🌐 Mermaid Live Editor Integration</h3>
            <p>Each diagram below can be opened directly in <a href="https://mermaid.live/" target="_blank">Mermaid Live Editor</a> for:</p>
            <ul>
                <li>🎨 Custom themes and colors</li>
                <li>📱 Mobile-friendly editing</li>
                <li>💾 Export as PNG, SVG, or PDF</li>
                <li>🔗 Share with team members</li>
                <li>🔄 Real-time preview</li>
                <li>📋 Copy and paste functionality</li>
            </ul>
        </div>
        
        <div class="diagram-grid">
            <div class="diagram-card">
                <div class="diagram-title">🏗️ System Architecture</div>
                <div class="diagram-description">Complete system map with all services and connections</div>
                <a href="01-system-architecture.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">🔄 User Journey</div>
                <div class="diagram-description">End-to-end user interaction flow</div>
                <a href="02-user-journey.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">📊 Data Flow</div>
                <div class="diagram-description">Comprehensive data processing paths</div>
                <a href="03-data-flow.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">💬 Web Chat</div>
                <div class="diagram-description">Real-time chat interaction flow</div>
                <a href="04-web-chat.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">📱 Chat Adapters</div>
                <div class="diagram-description">Multi-platform chat integration</div>
                <a href="05-chat-adapters.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">📥 Document Ingestion</div>
                <div class="diagram-description">Document processing and indexing</div>
                <a href="06-document-ingestion.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">🔍 Retrieval</div>
                <div class="diagram-description">Knowledge search and retrieval</div>
                <a href="07-retrieval.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
            
            <div class="diagram-card">
                <div class="diagram-title">📊 Billing & Analytics</div>
                <div class="diagram-description">Usage tracking and billing flow</div>
                <a href="08-billing-analytics.html" class="view-btn">📖 View</a>
                <a href="https://mermaid.live/" target="_blank" class="view-btn live-editor-btn">🌐 Live Editor</a>
            </div>
        </div>
        
        <div class="instructions">
            <h3>🚀 Quick Start</h3>
            <ol>
                <li>Click "Live Editor" on any diagram above</li>
                <li>Copy the diagram code from the "View" page</li>
                <li>Paste into Mermaid Live Editor</li>
                <li>Customize themes and export</li>
            </ol>
        </div>
    </div>
</body>
</html>
EOF

# Create script to open Live Editor with specific diagram
cat > docs/flows/live-editor/open-live-editor.sh << 'EOF'
#!/bin/bash

# 🌐 Open Mermaid Live Editor with specific diagram
# Usage: ./open-live-editor.sh <diagram-name>

if [ $# -eq 0 ]; then
    echo "🌐 Opening Mermaid Live Editor..."
    open "https://mermaid.live/"
else
    DIAGRAM_NAME="$1"
    DIAGRAM_FILE="docs/flows/live-editor/${DIAGRAM_NAME}.mmd"
    
    if [ -f "$DIAGRAM_FILE" ]; then
        echo "📊 Opening $DIAGRAM_NAME in Mermaid Live Editor..."
        
        # Copy diagram to clipboard (macOS)
        if command -v pbcopy &> /dev/null; then
            cat "$DIAGRAM_FILE" | pbcopy
            echo "✅ Diagram code copied to clipboard!"
        fi
        
        # Open Live Editor
        open "https://mermaid.live/"
        
        echo "💡 Paste the diagram code into Mermaid Live Editor"
    else
        echo "❌ Diagram not found: $DIAGRAM_FILE"
        echo "📋 Available diagrams:"
        ls docs/flows/live-editor/*.mmd | sed 's/.*\///; s/.mmd$//' | sed 's/^/   • /'
    fi
fi
EOF

chmod +x docs/flows/live-editor/open-live-editor.sh

# Create batch copy script
cat > docs/flows/live-editor/copy-all-diagrams.sh << 'EOF'
#!/bin/bash

# 📋 Copy all diagrams to clipboard for Mermaid Live Editor

echo "📋 Copying all diagrams to clipboard..."

# Create a combined file
cat > /tmp/all-diagrams.txt << 'EOF2'
# Multi-AI-Agent Platform - All Diagrams for Mermaid Live Editor

## 1. System Architecture
EOF2

cat docs/flows/live-editor/01-system-architecture.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 2. User Journey
EOF2

cat docs/flows/live-editor/02-user-journey.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 3. Data Flow
EOF2

cat docs/flows/live-editor/03-data-flow.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 4. Web Chat
EOF2

cat docs/flows/live-editor/04-web-chat.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 5. Chat Adapters
EOF2

cat docs/flows/live-editor/05-chat-adapters.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 6. Document Ingestion
EOF2

cat docs/flows/live-editor/06-document-ingestion.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 7. Retrieval
EOF2

cat docs/flows/live-editor/07-retrieval.mmd >> /tmp/all-diagrams.txt

cat >> /tmp/all-diagrams.txt << 'EOF2'

## 8. Billing & Analytics
EOF2

cat docs/flows/live-editor/08-billing-analytics.mmd >> /tmp/all-diagrams.txt

# Copy to clipboard
if command -v pbcopy &> /dev/null; then
    cat /tmp/all-diagrams.txt | pbcopy
    echo "✅ All diagrams copied to clipboard!"
    echo "🌐 Now open https://mermaid.live/ and paste"
elif command -v xclip &> /dev/null; then
    cat /tmp/all-diagrams.txt | xclip -selection clipboard
    echo "✅ All diagrams copied to clipboard!"
    echo "🌐 Now open https://mermaid.live/ and paste"
else
    echo "📄 Diagrams saved to: /tmp/all-diagrams.txt"
    echo "🌐 Copy the content and paste into https://mermaid.live/"
fi

rm /tmp/all-diagrams.txt
EOF

chmod +x docs/flows/live-editor/copy-all-diagrams.sh

echo "✅ Mermaid Live Editor setup complete!"
echo ""
echo "📁 Created files in docs/flows/live-editor/:"
echo "   • index.html - Main dashboard"
echo "   • 01-system-architecture.html - System architecture diagram"
echo "   • 02-user-journey.html - User journey diagram"
echo "   • 03-data-flow.html - Data flow diagram"
echo "   • 04-web-chat.html - Web chat diagram"
echo "   • 05-chat-adapters.html - Chat adapters diagram"
echo "   • 06-document-ingestion.html - Document ingestion diagram"
echo "   • 07-retrieval.html - Retrieval diagram"
echo "   • 08-billing-analytics.html - Billing & analytics diagram"
echo "   • open-live-editor.sh - Script to open specific diagrams"
echo "   • copy-all-diagrams.sh - Script to copy all diagrams"
echo ""
echo "🚀 How to use:"
echo "   1. Open: open docs/flows/live-editor/index.html"
echo "   2. Or run: ./docs/flows/live-editor/open-live-editor.sh"
echo "   3. Or run: ./docs/flows/live-editor/copy-all-diagrams.sh"
echo ""
echo "🎯 Features:"
echo "   • Individual diagram pages with copy buttons"
echo "   • Direct links to Mermaid Live Editor"
echo "   • Mobile-friendly interface"
echo "   • Batch copy functionality"
echo "   • Custom themes and export options"
