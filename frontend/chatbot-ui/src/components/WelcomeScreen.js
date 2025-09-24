import React from 'react';
import { Bot, Search, BookOpen, Lightbulb, MessageCircle } from 'lucide-react';

const WelcomeScreen = () => {
  const exampleQuestions = [
    "What is artificial intelligence?",
    "How does machine learning work?",
    "Explain quantum computing",
    "What are the benefits of renewable energy?",
    "How do neural networks learn?"
  ];

  const features = [
    {
      icon: <Search className="w-6 h-6" />,
      title: "Intelligent Search",
      description: "Get comprehensive answers with multiple sources"
    },
    {
      icon: <BookOpen className="w-6 h-6" />,
      title: "Source Citations",
      description: "Every answer includes verified sources and references"
    },
    {
      icon: <Lightbulb className="w-6 h-6" />,
      title: "Step-by-Step Process",
      description: "See how the AI approaches and solves your questions"
    },
    {
      icon: <MessageCircle className="w-6 h-6" />,
      title: "Natural Conversation",
      description: "Chat naturally and get detailed explanations"
    }
  ];

  return (
    <div className="text-center py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="w-20 h-20 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <Bot className="w-10 h-10 text-primary-600" />
        </div>
        
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          Welcome to AI Search Agent
        </h2>
        
        <p className="text-lg text-gray-600 mb-8">
          Your intelligent research assistant that provides comprehensive answers 
          with sources, citations, and step-by-step reasoning.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {features.map((feature, index) => (
            <div key={index} className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg text-left">
              <div className="text-primary-600 flex-shrink-0 mt-1">
                {feature.icon}
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 mb-1">{feature.title}</h3>
                <p className="text-sm text-gray-600">{feature.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Try asking:</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {exampleQuestions.map((question, index) => (
              <button
                key={index}
                className="text-left p-3 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200 hover:border-primary-300 transition-colors"
                onClick={() => {
                  const input = document.querySelector('textarea');
                  if (input) {
                    input.value = question;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                  }
                }}
              >
                "{question}"
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;




