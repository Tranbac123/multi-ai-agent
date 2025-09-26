# 🎨 VS Code Setup for High-Resolution Mermaid Viewing

## 📋 **Quick Setup**

### 1. Install VS Code Extensions
```bash
# Install Mermaid extension
code --install-extension bierner.markdown-mermaid

# Install Markdown Preview Enhanced
code --install-extension shd101wyy.markdown-preview-enhanced
```

### 2. Open Mermaid Files
```bash
# Open VS Code in the flows directory
cd docs/flows/
code .
```

### 3. View Diagrams
- Open any `.mmd` file in VS Code
- Press `Ctrl+Shift+V` (or `Cmd+Shift+V` on Mac) to open preview
- Use `Ctrl+K V` (or `Cmd+K V` on Mac) to open side-by-side preview

## 🎯 **Advanced Features**

### High-Resolution Export
1. Open any `.mmd` file
2. Right-click in the preview
3. Select "Export as Image"
4. Choose format: PNG, SVG, or PDF
5. Set high resolution (2x or 3x scaling)

### Interactive Preview
- Hover over nodes to see details
- Click to zoom in/out
- Pan around large diagrams
- Full-screen mode available

## 🌐 **Alternative: Mermaid Live Editor**

### Online Viewing (No Installation Required)
1. Go to [Mermaid Live Editor](https://mermaid.live/)
2. Copy content from any `.mmd` file
3. Paste into the editor
4. View high-resolution diagram
5. Export as PNG/SVG with custom resolution

### Usage Example:
```bash
# Copy content from file
cat docs/flows/detailed-visual-flow.mmd | pbcopy  # Mac
cat docs/flows/detailed-visual-flow.mmd | xclip   # Linux
```

## 📱 **Mobile-Friendly Solutions**

### GitHub Rendering
- Push `.mmd` files to GitHub
- GitHub automatically renders Mermaid diagrams
- Works on mobile devices
- High-resolution viewing

### Notion Integration
- Import `.mmd` files into Notion
- Notion renders Mermaid diagrams
- Mobile-friendly interface
- Collaborative viewing

## 🎨 **Custom Rendering Options**

### High-Resolution CLI Rendering
```bash
# Ultra-high resolution (4K)
mmdc -i detailed-visual-flow.mmd -o detailed-visual-flow-4K.png \
     -t dark -b white -s 4 -w 4000 -H 3000

# Vector format (scalable)
mmdc -i detailed-visual-flow.mmd -o detailed-visual-flow.svg \
     -t dark -b white

# PDF format (printable)
mmdc -i detailed-visual-flow.mmd -o detailed-visual-flow.pdf \
     -t dark -b white -s 2
```

### Batch High-Resolution Rendering
```bash
# Render all diagrams in high resolution
for file in *.mmd; do
    echo "Rendering $file in 4K..."
    mmdc -i "$file" -o "${file%.mmd}-4K.png" \
         -t dark -b white -s 4 -w 4000 -H 3000
done
```

## 💡 **Pro Tips**

1. **Use SVG format** for best scalability
2. **Set custom dimensions** for specific use cases
3. **Try different themes** for better contrast
4. **Use full-screen mode** for detailed viewing
5. **Export as PDF** for presentations

## 🔧 **Troubleshooting**

### If diagrams don't render:
1. Check Mermaid syntax
2. Ensure proper file encoding (UTF-8)
3. Update Mermaid CLI version
4. Try different themes

### For mobile viewing:
1. Use Mermaid Live Editor
2. GitHub rendering
3. Notion integration
4. Export as high-res PNG
