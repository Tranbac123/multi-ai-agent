# 🎨 High-Resolution Mermaid Diagram Viewing Guide

## 🚀 **Quick Solutions (Choose Your Preferred Method)**

### **Method 1: Ultra-High Resolution PNG (Recommended)**

```bash
# Render in 4K resolution (2.5MB file, crystal clear)
mmdc -i docs/flows/detailed-visual-flow.mmd -o docs/flows/detailed-visual-flow-ULTRA-HD.png -t dark -b white -s 4 -w 4000 -H 3000

# Open in any image viewer (Preview, Photoshop, GIMP, etc.)
open docs/flows/detailed-visual-flow-ULTRA-HD.png
```

### **Method 2: VS Code Extension (Best for Development)**

```bash
# Install Mermaid extension
code --install-extension bierner.markdown-mermaid

# Open VS Code in flows directory
cd docs/flows/
code .

# Open any .mmd file and press Ctrl+Shift+V for preview
# Right-click in preview → "Export as Image" → Choose high resolution
```

### **Method 3: Mermaid Live Editor (No Installation)**

1. Go to [Mermaid Live Editor](https://mermaid.live/)
2. Copy content from any `.mmd` file:
   ```bash
   cat docs/flows/detailed-visual-flow.mmd | pbcopy  # Mac
   ```
3. Paste into editor
4. Export as PNG/SVG with custom resolution
5. Download high-resolution image

### **Method 4: Interactive HTML Viewer**

```bash
# Open the interactive HTML viewer
open docs/flows/view-diagrams.html
# Features: Zoom, theme switching, fullscreen mode
```

## 📊 **File Size Comparison**

| Format       | Size   | Resolution  | Best For          |
| ------------ | ------ | ----------- | ----------------- |
| Default PNG  | 45KB   | ~800x600    | Quick preview     |
| HD PNG       | 1.2MB  | ~2000x1500  | Documentation     |
| Ultra-HD PNG | 2.5MB  | 4000x3000   | **Presentations** |
| SVG          | ~500KB | Vector      | **Web/Scaling**   |
| PDF          | ~1MB   | Print-ready | **Printing**      |

## 🎯 **Recommended Workflow**

### For **Presentations & Documentation**:

```bash
# Use ultra-high resolution PNG
./docs/flows/render-ultra-hd.sh
# Opens docs/flows/rendered/4K/ folder with 4K images
```

### For **Development & Editing**:

```bash
# Use VS Code with Mermaid extension
code docs/flows/
# Open .mmd files, live preview with Ctrl+Shift+V
```

### For **Web & Mobile Viewing**:

```bash
# Use SVG format (scalable)
mmdc -i docs/flows/detailed-visual-flow.mmd -o docs/flows/detailed-visual-flow.svg -t dark -b white
# Open in web browser - infinitely scalable
```

### For **Quick Sharing**:

```bash
# Use Mermaid Live Editor
# Copy .mmd content → Paste → Export → Share link
```

## 🛠️ **Advanced Rendering Options**

### Custom Dimensions

```bash
# For specific use cases
mmdc -i input.mmd -o output.png -w 1920 -H 1080 -s 2  # Full HD
mmdc -i input.mmd -o output.png -w 2560 -H 1440 -s 2  # 2K
mmdc -i input.mmd -o output.png -w 3840 -H 2160 -s 2  # 4K
```

### Different Themes

```bash
# Try different themes for better contrast
mmdc -i input.mmd -o output.png -t dark     # Dark theme
mmdc -i input.mmd -o output.png -t forest   # Forest theme
mmdc -i input.mmd -o output.png -t neutral  # Neutral theme
```

### Vector Format (Best Quality)

```bash
# SVG is infinitely scalable
mmdc -i input.mmd -o output.svg -t dark -b white
# Perfect for any resolution, small file size
```

## 📱 **Mobile-Friendly Solutions**

1. **GitHub Rendering**: Push `.mmd` files to GitHub, view on mobile
2. **Mermaid Live Editor**: Mobile-friendly web interface
3. **SVG Format**: Opens in mobile browsers, pinch-to-zoom
4. **PDF Format**: Mobile PDF viewers with zoom

## 🎨 **Pro Tips**

1. **Use SVG for best quality** - infinitely scalable
2. **4K PNG for presentations** - crystal clear on large screens
3. **VS Code for development** - live preview while editing
4. **Mermaid Live for sharing** - no installation required
5. **Different themes** - try dark/forest for better contrast

## 🔧 **Troubleshooting**

### If images are still blurry:

- Use SVG format (vector graphics)
- Increase scale factor: `-s 4` or `-s 6`
- Set custom dimensions: `-w 4000 -H 3000`

### If VS Code extension doesn't work:

- Install: `bierner.markdown-mermaid`
- Restart VS Code
- Check file encoding (UTF-8)

### If Mermaid Live Editor is slow:

- Use smaller diagrams
- Try different themes
- Export as SVG instead of PNG

## 📁 **Generated Files Location**

```
docs/flows/
├── rendered/
│   ├── 4K/           # 4K resolution PNG files
│   ├── 8K/           # 8K resolution PNG files
│   ├── SVG/          # Vector SVG files
│   └── PDF/          # Printable PDF files
├── *.png             # Standard resolution files
├── *.svg             # Vector files
└── *.pdf             # PDF files
```

## 🎯 **Quick Commands**

```bash
# Render all diagrams in ultra-high resolution
./docs/flows/render-ultra-hd.sh

# Render single diagram in 4K
mmdc -i docs/flows/detailed-visual-flow.mmd -o output-4K.png -s 4 -w 4000 -H 3000

# Open interactive viewer
open docs/flows/view-diagrams.html

# Open VS Code for live editing
code docs/flows/
```
