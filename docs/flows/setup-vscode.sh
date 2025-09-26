#!/bin/bash

# 🔧 VS Code Setup Script for Mermaid Diagrams
# This script sets up VS Code for optimal Mermaid diagram viewing

set -e

echo "🔧 Setting up VS Code for Mermaid diagrams..."

# Check if VS Code is installed
if ! command -v code &> /dev/null; then
    echo "❌ VS Code is not installed or not in PATH"
    echo "📥 Please install VS Code from: https://code.visualstudio.com/"
    echo "🔧 Or install via Homebrew: brew install --cask visual-studio-code"
    exit 1
fi

echo "✅ VS Code found, installing extensions..."

# Install required extensions
echo "📦 Installing Mermaid extension..."
code --install-extension bierner.markdown-mermaid --force

echo "📦 Installing additional helpful extensions..."
code --install-extension ms-vscode.vscode-json --force
code --install-extension redhat.vscode-yaml --force
code --install-extension ms-python.python --force

echo "🎨 Creating VS Code workspace configuration..."

# Create workspace file
cat > docs/flows/mermaid-diagrams.code-workspace << 'EOF'
{
  "folders": [
    {
      "path": "."
    }
  ],
  "settings": {
    "markdown.mermaid.theme": "dark",
    "markdown.preview.breaks": true,
    "markdown.preview.linkify": true,
    "markdown.preview.typographer": true,
    "markdown.extension.toc.levels": "1..6",
    "markdown.extension.toc.orderedList": false,
    "markdown.extension.toc.updateOnSave": true,
    "files.associations": {
      "*.mmd": "mermaid"
    },
    "mermaid.theme": "dark",
    "mermaid.themeVariables": {
      "primaryColor": "#ff6b6b",
      "primaryTextColor": "#ffffff",
      "primaryBorderColor": "#ff4757",
      "lineColor": "#ffffff",
      "secondaryColor": "#70a1ff",
      "tertiaryColor": "#5352ed"
    }
  },
  "extensions": {
    "recommendations": [
      "bierner.markdown-mermaid",
      "ms-vscode.vscode-json",
      "redhat.vscode-yaml",
      "ms-python.python"
    ]
  }
}
EOF

echo "🚀 Opening VS Code workspace..."

# Open VS Code with the workspace
code docs/flows/mermaid-diagrams.code-workspace

echo "✅ VS Code setup complete!"
echo ""
echo "📋 How to use:"
echo "   1. VS Code should open with the Mermaid workspace"
echo "   2. Open SERVICE_FLOWS.md"
echo "   3. Press Ctrl+Shift+V (Cmd+Shift+V on Mac) for preview"
echo "   4. Diagrams will render automatically with dark theme"
echo ""
echo "🎨 Features enabled:"
echo "   • Dark theme for better contrast"
echo "   • Syntax highlighting for Mermaid"
echo "   • Live preview with auto-refresh"
echo "   • Export to PNG/SVG from preview"
echo "   • Table of contents generation"
echo ""
echo "💡 Pro tips:"
echo "   • Right-click in preview → 'Export as Image'"
echo "   • Use Ctrl+K V for side-by-side preview"
echo "   • Edit diagrams and see live updates"
echo "   • Use Ctrl+Shift+P → 'Markdown: Open Preview to the Side'"
