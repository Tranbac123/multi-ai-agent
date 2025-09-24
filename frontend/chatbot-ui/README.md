# AI Search Agent - React Frontend

A modern, ChatGPT-like web interface for the AI Search Agent built with React and Tailwind CSS.

## Features

- **Modern Chat Interface**: Clean, responsive design similar to ChatGPT
- **Real-time Messaging**: Instant responses with loading indicators
- **Source Citations**: Display sources and references for each answer
- **Process Tracing**: Show step-by-step reasoning process
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Error Handling**: Graceful error handling with user-friendly messages
- **Welcome Screen**: Interactive welcome with example questions

## Quick Start

### Prerequisites

- Node.js 16+ and npm
- AI Search Agent API running on port 8000

### Installation

```bash
# Install dependencies
npm install

# Copy environment configuration
cp env.example .env

# Start development server
npm start
```

The app will open at `http://localhost:3000`

### Production Build

```bash
# Build for production
npm run build

# Serve the build
npx serve -s build
```

## Configuration

### Environment Variables

| Variable            | Description     | Default                 |
| ------------------- | --------------- | ----------------------- |
| `REACT_APP_API_URL` | Backend API URL | `http://localhost:8000` |

### API Integration

The frontend expects the backend API to have these endpoints:

- **GET** `/healthz` - Health check
- **POST** `/ask` - Ask a question

Request format:

```json
{
  "query": "What is artificial intelligence?",
  "session_id": "optional_session_id"
}
```

Response format:

```json
{
  "answer": "AI is a branch of computer science...",
  "citations": ["[1] https://example.com"],
  "trace": ["Planning: Search strategy...", "Sources found: 3"]
}
```

## Project Structure

```
frontend/
├── public/
│   └── index.html              # HTML template
├── src/
│   ├── components/             # React components
│   │   ├── ChatInput.js        # Message input component
│   │   ├── LoadingMessage.js   # Loading indicator
│   │   ├── MessageBubble.js    # Message display component
│   │   └── WelcomeScreen.js    # Welcome screen
│   ├── hooks/                  # Custom React hooks
│   │   └── useChat.js          # Chat state management
│   ├── services/               # API services
│   │   └── api.js              # API client
│   ├── App.js                  # Main app component
│   ├── index.js                # App entry point
│   └── index.css               # Global styles
├── package.json                # Dependencies and scripts
├── tailwind.config.js          # Tailwind CSS configuration
└── postcss.config.js           # PostCSS configuration
```

## Components

### App.js

Main application component that orchestrates the chat interface.

### MessageBubble.js

Displays individual messages with support for:

- User and assistant messages
- Source citations with clickable links
- Process trace information
- Error messages

### ChatInput.js

Input component with:

- Auto-resizing textarea
- Send button with loading state
- Keyboard shortcuts (Enter to send, Shift+Enter for new line)

### WelcomeScreen.js

Interactive welcome screen with:

- Feature highlights
- Example questions
- Click-to-ask functionality

### useChat.js

Custom hook for chat state management:

- Message history
- Loading states
- Error handling
- API integration

## Styling

The app uses Tailwind CSS with a custom design system:

- **Primary Colors**: Blue theme with various shades
- **Typography**: Clean, readable fonts
- **Spacing**: Consistent spacing system
- **Animations**: Smooth transitions and loading states
- **Responsive**: Mobile-first responsive design

## Development

### Available Scripts

- `npm start` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App

### Code Structure

The app follows React best practices:

- **Functional Components**: All components use React hooks
- **Custom Hooks**: Reusable state logic
- **Component Composition**: Small, focused components
- **Props Validation**: Type checking with PropTypes
- **Error Boundaries**: Graceful error handling

## API Integration

### Error Handling

The app handles various error scenarios:

- **Network Errors**: Connection issues
- **API Errors**: Server-side errors
- **Validation Errors**: Invalid responses
- **Timeout Errors**: Request timeouts

### Loading States

- **Message Loading**: Animated dots while waiting for response
- **Button States**: Disabled state during requests
- **Input States**: Disabled input during processing

## Deployment

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npx", "serve", "-s", "build"]
```

### Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/build;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Performance

- **Code Splitting**: Automatic code splitting with React.lazy
- **Bundle Optimization**: Optimized production builds
- **Image Optimization**: Optimized assets
- **Caching**: Proper cache headers

## Security

- **XSS Protection**: Sanitized user input
- **CSRF Protection**: Secure API calls
- **Content Security Policy**: Restricted resource loading
- **HTTPS**: Secure connections in production

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is part of the AI Search Agent and follows the same license terms.




