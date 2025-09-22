import React, { useState, useEffect } from 'react';
import { UserSubscription, UsageStats, ServicePackage, PackageType, BillingCycle } from '../types/subscription';

interface SubscriptionDashboardProps {
  userId: number;
}

const SubscriptionDashboard: React.FC<SubscriptionDashboardProps> = ({ userId }) => {
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [packages, setPackages] = useState<ServicePackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSubscriptionData();
  }, [userId]);

  const fetchSubscriptionData = async () => {
    try {
      setLoading(true);
      
      // Fetch subscription
      const subscriptionResponse = await fetch('/api/subscription', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (subscriptionResponse.ok) {
        const subscriptionData = await subscriptionResponse.json();
        setSubscription(subscriptionData);
      }

      // Fetch usage stats
      const usageResponse = await fetch('/api/usage', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (usageResponse.ok) {
        const usageData = await usageResponse.json();
        setUsageStats(usageData);
      }

      // Fetch available packages
      const packagesResponse = await fetch('/api/packages');
      if (packagesResponse.ok) {
        const packagesData = await packagesResponse.json();
        setPackages(packagesData);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch subscription data');
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (packageType: PackageType, billingCycle: BillingCycle) => {
    try {
      const response = await fetch('/api/subscription/upgrade', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          package_type: packageType,
          billing_cycle: billingCycle
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.payment_required) {
          // Redirect to payment page
          window.location.href = result.payment_url;
        } else {
          // Refresh subscription data
          await fetchSubscriptionData();
        }
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upgrade failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upgrade failed');
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel your subscription?')) {
      return;
    }

    try {
      const response = await fetch('/api/subscription/cancel', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });

      if (response.ok) {
        await fetchSubscriptionData();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Cancellation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancellation failed');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!subscription) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-600">No subscription found</p>
      </div>
    );
  }

  const currentPackage = subscription.package;
  const isTrial = subscription.is_trial;
  const isActive = subscription.is_active;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Current Subscription */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-900">Current Subscription</h2>
          <div className="flex space-x-2">
            {isTrial && (
              <span className="bg-yellow-100 text-yellow-800 px-3 py-1 rounded-full text-sm font-medium">
                Trial
              </span>
            )}
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}>
              {isActive ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">{currentPackage.name}</h3>
            <p className="text-gray-600 text-sm mb-4">{currentPackage.description}</p>
            <div className="text-2xl font-bold text-gray-900">
              ${currentPackage.price_monthly}
              <span className="text-sm text-gray-600">/month</span>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-gray-900 mb-2">Billing Cycle</h4>
            <p className="text-gray-600 capitalize">{subscription.billing_cycle}</p>
            
            <h4 className="font-semibold text-gray-900 mb-2 mt-4">Next Billing Date</h4>
            <p className="text-gray-600">
              {subscription.end_date ? new Date(subscription.end_date).toLocaleDateString() : 'N/A'}
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-gray-900 mb-2">Subscription Status</h4>
            <p className="text-gray-600 capitalize">{subscription.status}</p>
            
            {subscription.trial_end_date && (
              <>
                <h4 className="font-semibold text-gray-900 mb-2 mt-4">Trial Ends</h4>
                <p className="text-gray-600">
                  {new Date(subscription.trial_end_date).toLocaleDateString()}
                </p>
              </>
            )}
          </div>
        </div>

        {!isActive && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-red-800 text-sm">
              Your subscription is inactive. Please upgrade or contact support.
            </p>
          </div>
        )}
      </div>

      {/* Usage Statistics */}
      {usageStats && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Usage Statistics</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Messages */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <h3 className="font-semibold text-gray-900">Messages</h3>
                <span className="text-sm text-gray-600">
                  {usageStats.messages_used_this_month.toLocaleString()} / {usageStats.messages_limit.toLocaleString()}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    usageStats.is_over_limit ? 'bg-red-500' : 
                    usageStats.is_near_limit ? 'bg-yellow-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min(usageStats.messages_usage_percent, 100)}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-600 mt-1">
                {usageStats.messages_usage_percent.toFixed(1)}% used
              </p>
            </div>

            {/* Customers */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <h3 className="font-semibold text-gray-900">Customers</h3>
                <span className="text-sm text-gray-600">
                  {usageStats.customers_created.toLocaleString()} / {usageStats.customers_limit.toLocaleString()}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    usageStats.is_over_limit ? 'bg-red-500' : 
                    usageStats.is_near_limit ? 'bg-yellow-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min(usageStats.customers_usage_percent, 100)}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-600 mt-1">
                {usageStats.customers_usage_percent.toFixed(1)}% used
              </p>
            </div>

            {/* Storage */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <h3 className="font-semibold text-gray-900">Storage</h3>
                <span className="text-sm text-gray-600">
                  {usageStats.storage_used_gb.toFixed(1)}GB / {usageStats.storage_limit_gb}GB
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    usageStats.is_over_limit ? 'bg-red-500' : 
                    usageStats.is_near_limit ? 'bg-yellow-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min(usageStats.storage_usage_percent, 100)}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-600 mt-1">
                {usageStats.storage_usage_percent.toFixed(1)}% used
              </p>
            </div>
          </div>

          {usageStats.is_near_limit && (
            <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-yellow-800 text-sm">
                You're approaching your usage limits. Consider upgrading your plan.
              </p>
            </div>
          )}

          {usageStats.is_over_limit && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-800 text-sm">
                You've exceeded your usage limits. Please upgrade your plan to continue using the service.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Available Packages */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Available Plans</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {packages.map((pkg) => {
            const isCurrentPackage = pkg.package_type === currentPackage.package_type;
            const isUpgrade = pkg.package_type !== PackageType.FREE && 
                            (currentPackage.package_type === PackageType.FREE || 
                             pkg.price_monthly > currentPackage.price_monthly);
            
            return (
              <div
                key={pkg.id}
                className={`relative border-2 rounded-lg p-6 ${
                  isCurrentPackage 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                {isCurrentPackage && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <span className="bg-blue-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                      Current Plan
                    </span>
                  </div>
                )}

                <div className="text-center mb-4">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">{pkg.name}</h3>
                  <p className="text-gray-600 text-sm mb-4">{pkg.description}</p>
                  <div className="text-3xl font-bold text-gray-900">
                    ${pkg.price_monthly}
                    <span className="text-sm text-gray-600">/month</span>
                  </div>
                </div>

                <div className="space-y-2 mb-6">
                  <div className="flex items-center text-sm text-gray-600">
                    <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {pkg.max_messages_per_month.toLocaleString()} messages/month
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {pkg.max_customers.toLocaleString()} customers
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {pkg.max_agents} agent{pkg.max_agents > 1 ? 's' : ''}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {pkg.max_storage_gb}GB storage
                  </div>
                </div>

                {!isCurrentPackage && (
                  <button
                    onClick={() => handleUpgrade(pkg.package_type, BillingCycle.MONTHLY)}
                    className={`w-full py-2 px-4 rounded-md font-medium transition-colors ${
                      isUpgrade
                        ? 'bg-blue-600 text-white hover:bg-blue-700'
                        : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                    }`}
                  >
                    {isUpgrade ? 'Upgrade' : 'Downgrade'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Account Actions</h2>
        
        <div className="flex space-x-4">
          <button
            onClick={handleCancel}
            className="bg-red-600 text-white px-4 py-2 rounded-md font-medium hover:bg-red-700 transition-colors"
          >
            Cancel Subscription
          </button>
          
          <button
            onClick={() => window.open('/contact', '_blank')}
            className="bg-gray-600 text-white px-4 py-2 rounded-md font-medium hover:bg-gray-700 transition-colors"
          >
            Contact Support
          </button>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionDashboard;
