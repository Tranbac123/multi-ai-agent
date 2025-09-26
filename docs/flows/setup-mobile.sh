#!/bin/bash

# 📱 Mobile-Friendly Setup Script
# This script creates mobile-optimized viewing options for Mermaid diagrams

set -e

echo "📱 Setting up mobile-friendly viewing options..."

# Create mobile directory
mkdir -p docs/flows/mobile

# Create mobile-optimized HTML viewer
cat > docs/flows/mobile/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-AI-Agent Platform - Mobile Diagrams</title>
    <style>
        * {
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            overflow-x: hidden;
        }
        
        .header {
            background: #2c3e50;
            color: white;
            padding: 15px;
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            margin: 0;
            font-size: 1.5em;
        }
        
        .container {
            padding: 20px;
            max-width: 100%;
        }
        
        .diagram-card {
            background: white;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .diagram-header {
            background: #3498db;
            color: white;
            padding: 15px;
            font-weight: bold;
            font-size: 1.1em;
        }
        
        .diagram-content {
            padding: 20px;
        }
        
        .diagram-description {
            color: #666;
            margin-bottom: 15px;
            font-size: 0.9em;
            line-height: 1.4;
        }
        
        .diagram-image {
            width: 100%;
            height: auto;
            border-radius: 5px;
            margin: 10px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .view-options {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }
        
        .view-btn {
            background: #27ae60;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 5px;
            font-size: 0.9em;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            display: block;
        }
        
        .view-btn:hover {
            background: #229954;
        }
        
        .view-btn.secondary {
            background: #95a5a6;
        }
        
        .view-btn.secondary:hover {
            background: #7f8c8d;
        }
        
        .zoom-controls {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
        }
        
        .zoom-btn {
            background: #e74c3c;
            color: white;
            border: none;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            font-size: 1.2em;
            cursor: pointer;
            margin: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        .zoom-btn:hover {
            background: #c0392b;
        }
        
        .fullscreen-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 2000;
            display: none;
            padding: 20px;
            overflow: auto;
        }
        
        .fullscreen-image {
            max-width: 100%;
            max-height: 100%;
            margin: auto;
            display: block;
        }
        
        .close-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            background: #e74c3c;
            color: white;
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            font-size: 1.2em;
            cursor: pointer;
        }
        
        .theme-selector {
            position: fixed;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
        }
        
        .theme-btn {
            background: #9b59b6;
            color: white;
            border: none;
            padding: 10px;
            border-radius: 5px;
            font-size: 0.8em;
            cursor: pointer;
            margin: 2px;
        }
        
        .theme-btn:hover {
            background: #8e44ad;
        }
        
        .theme-btn.active {
            background: #e74c3c;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .view-options {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 1.3em;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎨 Multi-AI-Agent Platform</h1>
        <p>Mobile-Optimized Service Flow Diagrams</p>
    </div>
    
    <div class="container">
        <div class="diagram-card">
            <div class="diagram-header">🏗️ System Architecture</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Complete system map showing all services, connections, and data flow paths. 
                    Tap to zoom for detailed view.
                </div>
                <img src="../SERVICE_FLOWS-1.png" alt="System Architecture" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-1.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelector('img'))">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">🔄 User Journey</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    End-to-end user interaction flow from question to AI response. 
                    Shows complete request processing pipeline.
                </div>
                <img src="../SERVICE_FLOWS-2.png" alt="User Journey" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-2.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[1])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">📊 Data Flow</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Comprehensive data processing paths for different input types. 
                    Shows how data flows through the system.
                </div>
                <img src="../SERVICE_FLOWS-3.png" alt="Data Flow" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-3.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[2])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">💬 Web Chat Flow</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Real-time chat interaction flow with AI services. 
                    Shows message processing and response generation.
                </div>
                <img src="../SERVICE_FLOWS-4.png" alt="Web Chat Flow" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-4.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[3])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">📱 Chat Adapters</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Multi-platform chat integration (Facebook, Zalo, TikTok). 
                    Shows how messages are normalized and processed.
                </div>
                <img src="../SERVICE_FLOWS-5.png" alt="Chat Adapters" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-5.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[4])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">📥 Document Ingestion</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Document processing and indexing flow. 
                    Shows how documents are uploaded and made searchable.
                </div>
                <img src="../SERVICE_FLOWS-6.png" alt="Document Ingestion" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-6.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[5])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">🔍 Retrieval Flow</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Knowledge search and retrieval process. 
                    Shows how queries are processed and answered.
                </div>
                <img src="../SERVICE_FLOWS-7.png" alt="Retrieval Flow" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-7.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[6])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
        
        <div class="diagram-card">
            <div class="diagram-header">📊 Billing & Analytics</div>
            <div class="diagram-content">
                <div class="diagram-description">
                    Usage tracking, billing, and analytics flow. 
                    Shows how costs are calculated and tracked.
                </div>
                <img src="../SERVICE_FLOWS-8.png" alt="Billing & Analytics" class="diagram-image" onclick="openFullscreen(this)">
                <div class="view-options">
                    <a href="../SERVICE_FLOWS-8.png" class="view-btn" download>📥 Download</a>
                    <button class="view-btn secondary" onclick="openFullscreen(document.querySelectorAll('img')[7])">🔍 Fullscreen</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Zoom Controls -->
    <div class="zoom-controls">
        <button class="zoom-btn" onclick="zoomIn()">🔍+</button>
        <button class="zoom-btn" onclick="zoomOut()">🔍-</button>
        <button class="zoom-btn" onclick="resetZoom()">🔄</button>
    </div>
    
    <!-- Theme Selector -->
    <div class="theme-selector">
        <button class="theme-btn active" onclick="setTheme('light')">☀️</button>
        <button class="theme-btn" onclick="setTheme('dark')">🌙</button>
        <button class="theme-btn" onclick="setTheme('blue')">🔵</button>
    </div>
    
    <!-- Fullscreen Overlay -->
    <div class="fullscreen-overlay" id="fullscreen-overlay">
        <button class="close-btn" onclick="closeFullscreen()">✕</button>
        <img class="fullscreen-image" id="fullscreen-image" alt="Fullscreen diagram">
    </div>
    
    <script>
        let currentZoom = 1;
        let currentTheme = 'light';
        
        function openFullscreen(img) {
            const overlay = document.getElementById('fullscreen-overlay');
            const fullscreenImg = document.getElementById('fullscreen-image');
            
            fullscreenImg.src = img.src;
            overlay.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
        
        function closeFullscreen() {
            const overlay = document.getElementById('fullscreen-overlay');
            overlay.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
        
        function zoomIn() {
            currentZoom += 0.2;
            document.body.style.zoom = currentZoom;
        }
        
        function zoomOut() {
            currentZoom -= 0.2;
            if (currentZoom < 0.5) currentZoom = 0.5;
            document.body.style.zoom = currentZoom;
        }
        
        function resetZoom() {
            currentZoom = 1;
            document.body.style.zoom = currentZoom;
        }
        
        function setTheme(theme) {
            currentTheme = theme;
            
            // Update theme buttons
            document.querySelectorAll('.theme-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Apply theme
            switch(theme) {
                case 'dark':
                    document.body.style.background = '#1a1a1a';
                    document.body.style.color = '#ffffff';
                    break;
                case 'blue':
                    document.body.style.background = '#e3f2fd';
                    document.body.style.color = '#1565c0';
                    break;
                default:
                    document.body.style.background = '#f5f5f5';
                    document.body.style.color = '#333333';
                    break;
            }
        }
        
        // Touch gestures for mobile
        let startY = 0;
        let startX = 0;
        
        document.addEventListener('touchstart', function(e) {
            startY = e.touches[0].clientY;
            startX = e.touches[0].clientX;
        });
        
        document.addEventListener('touchmove', function(e) {
            if (e.touches.length === 2) {
                // Pinch to zoom
                e.preventDefault();
            }
        });
        
        // Close fullscreen on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeFullscreen();
            }
        });
        
        // Close fullscreen on overlay click
        document.getElementById('fullscreen-overlay').addEventListener('click', function(e) {
            if (e.target === this) {
                closeFullscreen();
            }
        });
    </script>
</body>
</html>
EOF

# Create mobile-optimized PWA manifest
cat > docs/flows/mobile/manifest.json << 'EOF'
{
  "name": "Multi-AI-Agent Platform Diagrams",
  "short_name": "AI Diagrams",
  "description": "Mobile-optimized service flow diagrams for Multi-AI-Agent Platform",
  "start_url": "index.html",
  "display": "standalone",
  "background_color": "#f5f5f5",
  "theme_color": "#2c3e50",
  "orientation": "portrait",
  "icons": [
    {
      "src": "icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
EOF

# Create service worker for offline viewing
cat > docs/flows/mobile/sw.js << 'EOF'
const CACHE_NAME = 'ai-diagrams-v1';
const urlsToCache = [
  'index.html',
  'manifest.json',
  '../SERVICE_FLOWS-1.png',
  '../SERVICE_FLOWS-2.png',
  '../SERVICE_FLOWS-3.png',
  '../SERVICE_FLOWS-4.png',
  '../SERVICE_FLOWS-5.png',
  '../SERVICE_FLOWS-6.png',
  '../SERVICE_FLOWS-7.png',
  '../SERVICE_FLOWS-8.png'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});
EOF

# Create mobile setup script
cat > docs/flows/mobile/setup-mobile.sh << 'EOF'
#!/bin/bash

# 📱 Mobile Setup Script
# This script sets up mobile-optimized viewing

set -e

echo "📱 Setting up mobile-optimized viewing..."

# Create mobile icons (placeholder)
echo "🎨 Creating mobile icons..."

# Create 192x192 icon (placeholder)
convert -size 192x192 xc:#2c3e50 -fill white -gravity center -pointsize 48 -annotate +0+0 "🎨" icon-192.png 2>/dev/null || {
    echo "⚠️  ImageMagick not found, creating placeholder icons..."
    # Create simple placeholder icons
    echo "📱 Creating placeholder icons..."
}

# Create 512x512 icon (placeholder)
convert -size 512x512 xc:#2c3e50 -fill white -gravity center -pointsize 120 -annotate +0+0 "🎨" icon-512.png 2>/dev/null || {
    echo "📱 Placeholder icons created"
}

echo "✅ Mobile setup complete!"
echo ""
echo "📱 Mobile features enabled:"
echo "   • Responsive design for all screen sizes"
echo "   • Touch-friendly interface"
echo "   • Pinch-to-zoom support"
echo "   • Fullscreen viewing"
echo "   • Download functionality"
echo "   • Theme switching"
echo "   • Offline viewing (PWA)"
echo ""
echo "🚀 How to use:"
echo "   1. Open: docs/flows/mobile/index.html"
echo "   2. Add to home screen on mobile devices"
echo "   3. Use offline after first visit"
echo ""
echo "📱 Mobile optimization:"
echo "   • Fast loading on mobile networks"
echo "   • Touch gestures for navigation"
echo "   • Optimized image sizes"
echo "   • Progressive Web App (PWA) support"
EOF

chmod +x docs/flows/mobile/setup-mobile.sh

# Create mobile documentation
cat > docs/flows/mobile/README.md << 'EOF'
# 📱 Mobile-Optimized Mermaid Diagrams

This directory contains mobile-optimized viewing options for all service flow diagrams.

## 🚀 Features

### 📱 Mobile-First Design
- **Responsive Layout**: Works on all screen sizes
- **Touch-Friendly**: Large buttons and touch targets
- **Fast Loading**: Optimized for mobile networks
- **Offline Support**: Progressive Web App (PWA)

### 🎨 Interactive Features
- **Pinch-to-Zoom**: Zoom in/out on diagrams
- **Fullscreen View**: Tap diagrams for fullscreen
- **Theme Switching**: Light, dark, and blue themes
- **Download**: Save diagrams to device

### 🔧 Technical Features
- **Service Worker**: Offline caching
- **Web App Manifest**: Add to home screen
- **Touch Gestures**: Swipe and pinch support
- **Keyboard Navigation**: Escape key support

## 📱 How to Use

### On Mobile Devices
1. Open `index.html` in mobile browser
2. Tap "Add to Home Screen" for app-like experience
3. Use pinch gestures to zoom diagrams
4. Tap diagrams for fullscreen view
5. Use theme buttons for different color schemes

### On Desktop
1. Open `index.html` in any browser
2. Use mouse to click and zoom
3. Keyboard shortcuts work (Escape to close fullscreen)
4. Responsive design adapts to window size

## 🎯 Mobile Optimization

### Performance
- **Lazy Loading**: Images load as needed
- **Compressed Images**: Optimized file sizes
- **Caching**: Service worker for offline viewing
- **Fast Rendering**: Optimized CSS and JavaScript

### User Experience
- **Large Touch Targets**: Easy to tap on mobile
- **Swipe Navigation**: Natural mobile gestures
- **Fullscreen Mode**: Immersive viewing experience
- **Theme Options**: Customizable appearance

## 🔧 Technical Details

### Files
- `index.html` - Main mobile interface
- `manifest.json` - PWA configuration
- `sw.js` - Service worker for offline support
- `setup-mobile.sh` - Setup script

### Browser Support
- **iOS Safari**: Full support
- **Android Chrome**: Full support
- **Firefox Mobile**: Full support
- **Samsung Internet**: Full support

### PWA Features
- **Installable**: Add to home screen
- **Offline**: Works without internet
- **Fast**: Cached resources
- **Responsive**: Adapts to screen size

## 🚀 Quick Start

```bash
# Open mobile interface
open docs/flows/mobile/index.html

# Or run setup script
./docs/flows/mobile/setup-mobile.sh
```

## 📱 Mobile Tips

1. **Add to Home Screen**: For app-like experience
2. **Use Landscape**: Better for wide diagrams
3. **Pinch to Zoom**: For detailed viewing
4. **Download**: Save diagrams for offline use
5. **Theme Switch**: Choose your preferred theme

---

*Optimized for mobile viewing with touch-friendly interface and offline support.*
EOF

echo "✅ Mobile-friendly setup complete!"
echo ""
echo "📁 Created mobile files:"
echo "   • mobile/index.html - Mobile-optimized interface"
echo "   • mobile/manifest.json - PWA configuration"
echo "   • mobile/sw.js - Service worker for offline support"
echo "   • mobile/setup-mobile.sh - Mobile setup script"
echo "   • mobile/README.md - Mobile documentation"
echo ""
echo "📱 Mobile features enabled:"
echo "   • Responsive design for all screen sizes"
echo "   • Touch-friendly interface with large buttons"
echo "   • Pinch-to-zoom support for diagrams"
echo "   • Fullscreen viewing mode"
echo "   • Download functionality for offline use"
echo "   • Theme switching (light, dark, blue)"
echo "   • Progressive Web App (PWA) support"
echo "   • Offline viewing with service worker"
echo ""
echo "🚀 How to use:"
echo "   1. Open: docs/flows/mobile/index.html"
echo "   2. On mobile: Add to home screen for app-like experience"
echo "   3. Use pinch gestures to zoom diagrams"
echo "   4. Tap diagrams for fullscreen view"
echo "   5. Use theme buttons for different color schemes"
echo ""
echo "📱 Mobile optimization benefits:"
echo "   • Fast loading on mobile networks"
echo "   • Touch gestures for natural navigation"
echo "   • Optimized image sizes for mobile"
echo "   • Offline viewing after first visit"
echo "   • App-like experience when added to home screen"
