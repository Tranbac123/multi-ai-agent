import React from 'react';
import SubscriptionDashboard from '../components/SubscriptionDashboard';

const SubscriptionPage: React.FC = () => {
  // Get user ID from localStorage or context
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id;

  if (!userId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Authentication Required</h1>
          <p className="text-gray-600 mb-4">Please log in to view your subscription.</p>
          <a
            href="/login"
            className="bg-blue-600 text-white px-4 py-2 rounded-md font-medium hover:bg-blue-700 transition-colors"
          >
            Go to Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Subscription Management</h1>
          <p className="text-gray-600 mt-2">
            Manage your subscription, view usage, and upgrade your plan
          </p>
        </div>
        
        <SubscriptionDashboard userId={userId} />
      </div>
    </div>
  );
};

export default SubscriptionPage;
