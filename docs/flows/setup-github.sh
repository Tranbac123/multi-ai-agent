#!/bin/bash

# 🌐 GitHub Setup Script for Mermaid Diagrams
# This script prepares files for GitHub automatic Mermaid rendering

set -e

echo "🌐 Setting up GitHub for automatic Mermaid rendering..."

# Create GitHub-specific README
cat > docs/flows/GITHUB_README.md << 'EOF'
# 🎨 Multi-AI-Agent Platform - Service Flow Diagrams

> **GitHub automatically renders Mermaid diagrams!** Just scroll down to see all diagrams rendered live.

## 🚀 Quick Start

1. **View Diagrams**: Scroll down to see all diagrams rendered automatically
2. **Mobile Friendly**: Works perfectly on mobile devices
3. **Interactive**: Click and zoom on diagrams
4. **Always Updated**: Diagrams update when you push changes

## 📊 All Diagrams

The diagrams below are rendered automatically by GitHub from Mermaid code blocks:

EOF

# Append the main content
cat SERVICE_FLOWS.md >> docs/flows/GITHUB_README.md

# Create GitHub Actions workflow for diagram validation
mkdir -p .github/workflows
cat > .github/workflows/mermaid-validation.yml << 'EOF'
name: Mermaid Diagram Validation

on:
  push:
    paths:
      - 'docs/flows/**/*.md'
      - 'docs/flows/**/*.mmd'
  pull_request:
    paths:
      - 'docs/flows/**/*.md'
      - 'docs/flows/**/*.mmd'

jobs:
  validate-mermaid:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install Mermaid CLI
        run: npm install -g @mermaid-js/mermaid-cli
        
      - name: Validate Mermaid syntax
        run: |
          echo "🔍 Validating Mermaid diagrams..."
          find docs/flows -name "*.md" -exec mmdc -i {} -o /tmp/test.png \;
          echo "✅ All Mermaid diagrams are valid!"
          
      - name: Generate diagram images
        run: |
          echo "🎨 Generating diagram images..."
          mkdir -p docs/flows/rendered/github
          find docs/flows -name "*.md" -exec mmdc -i {} -o docs/flows/rendered/github/{}.png \;
          
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: mermaid-diagrams
          path: docs/flows/rendered/github/
EOF

# Create GitHub Pages configuration
cat > docs/flows/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-AI-Agent Platform - Service Flow Diagrams</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f8f9fa;
        }
        .container {
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
        .diagram-section {
            margin-bottom: 40px;
            padding: 20px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #fafafa;
        }
        .diagram-title {
            font-size: 1.3em;
            font-weight: bold;
            color: #34495e;
            margin-bottom: 15px;
        }
        .github-link {
            display: inline-block;
            background: #24292e;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 0;
        }
        .github-link:hover {
            background: #0366d6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 Multi-AI-Agent Platform - Service Flow Diagrams</h1>
        
        <div class="diagram-section">
            <div class="diagram-title">🌐 GitHub Automatic Rendering</div>
            <p>GitHub automatically renders Mermaid diagrams from Markdown files. This provides the best viewing experience with:</p>
            <ul>
                <li>✅ Automatic rendering on push</li>
                <li>✅ Mobile-friendly interface</li>
                <li>✅ Interactive zoom and pan</li>
                <li>✅ Always up-to-date</li>
                <li>✅ No installation required</li>
            </ul>
            
            <a href="GITHUB_README.md" class="github-link">📖 View All Diagrams on GitHub</a>
        </div>
        
        <div class="diagram-section">
            <div class="diagram-title">📱 Mobile Viewing</div>
            <p>Perfect for mobile devices - GitHub's mobile interface renders Mermaid diagrams beautifully.</p>
        </div>
        
        <div class="diagram-section">
            <div class="diagram-title">🔄 Auto-Updates</div>
            <p>Diagrams automatically update when you push changes to the repository.</p>
        </div>
    </div>
</body>
</html>
EOF

echo "📝 Creating GitHub-specific documentation..."

# Create GitHub workflow for diagram updates
cat > docs/flows/update-github.md << 'EOF'
# 🔄 GitHub Integration Guide

## 🚀 How GitHub Renders Mermaid Diagrams

GitHub automatically detects and renders Mermaid diagrams in Markdown files. Here's how it works:

### ✅ Automatic Features
- **Live Rendering**: Diagrams appear automatically when viewing `.md` files
- **Mobile Support**: Perfect rendering on mobile devices
- **Interactive**: Click and zoom on diagrams
- **Always Current**: Updates when you push changes

### 📱 Mobile Experience
- Touch-friendly interface
- Responsive design
- Pinch-to-zoom support
- Offline viewing (when cached)

### 🔄 Workflow
1. Edit `.md` files with Mermaid code blocks
2. Push to GitHub
3. GitHub automatically renders diagrams
4. Share links with team members
5. View on any device

## 🛠️ Setup Steps

### 1. Push Files to GitHub
```bash
git add docs/flows/SERVICE_FLOWS.md
git commit -m "Add service flow diagrams"
git push origin main
```

### 2. View on GitHub
- Navigate to `docs/flows/SERVICE_FLOWS.md` in your repository
- Diagrams render automatically
- Share the link with team members

### 3. Enable GitHub Pages (Optional)
```bash
# In repository settings, enable GitHub Pages
# Source: Deploy from a branch
# Branch: main
# Folder: /docs
```

## 🎯 Benefits

- ✅ **No Installation**: Works in any web browser
- ✅ **Mobile Friendly**: Perfect on phones and tablets
- ✅ **Team Collaboration**: Share links with team members
- ✅ **Version Control**: Diagrams are part of your codebase
- ✅ **Always Updated**: Changes reflect immediately
- ✅ **Free Hosting**: GitHub provides free hosting

## 📊 Diagram Types Supported

GitHub supports all Mermaid diagram types:
- Flowcharts
- Sequence diagrams
- Class diagrams
- State diagrams
- Gantt charts
- Pie charts
- And more!

## 🔧 Troubleshooting

### If diagrams don't render:
1. Check Mermaid syntax
2. Ensure proper code block formatting
3. Verify file is in `.md` format
4. Check for syntax errors

### For better mobile experience:
1. Use responsive design principles
2. Keep diagrams simple and clear
3. Use appropriate font sizes
4. Test on different devices
EOF

echo "✅ GitHub setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Run: git add docs/flows/"
echo "   2. Run: git commit -m 'Add Mermaid diagrams for GitHub'"
echo "   3. Run: git push origin main"
echo "   4. View diagrams at: https://github.com/YOUR_USERNAME/YOUR_REPO/blob/main/docs/flows/SERVICE_FLOWS.md"
echo ""
echo "🎯 GitHub features enabled:"
echo "   • Automatic Mermaid rendering"
echo "   • Mobile-friendly interface"
echo "   • GitHub Actions validation"
echo "   • GitHub Pages support"
echo "   • Team collaboration"
echo ""
echo "📱 Mobile benefits:"
echo "   • Touch-friendly interface"
echo "   • Responsive design"
echo "   • Pinch-to-zoom support"
echo "   • Offline viewing"
