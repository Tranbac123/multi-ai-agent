import React, { useState, useEffect } from 'react';
import { ServicePackage, PackageType, BillingCycle } from '../types/subscription';

interface PackageSelectorProps {
  onPackageSelect: (packageType: PackageType, billingCycle: BillingCycle) => void;
  selectedPackage?: PackageType;
  selectedBillingCycle?: BillingCycle;
}

const PackageSelector: React.FC<PackageSelectorProps> = ({
  onPackageSelect,
  selectedPackage = PackageType.FREE,
  selectedBillingCycle = BillingCycle.MONTHLY
}) => {
  const [packages, setPackages] = useState<ServicePackage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPackages();
  }, []);

  const fetchPackages = async () => {
    try {
      const response = await fetch('/api/packages');
      const data = await response.json();
      setPackages(data);
    } catch (error) {
      console.error('Failed to fetch packages:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPackageFeatures = (pkg: ServicePackage) => {
    const features = [];
    
    if (pkg.has_analytics) features.push('Advanced Analytics');
    if (pkg.has_file_upload) features.push('File Upload');
    if (pkg.has_webhook_support) features.push('Webhook Support');
    if (pkg.has_api_access) features.push('API Access');
    if (pkg.has_priority_support) features.push('Priority Support');
    if (pkg.has_custom_branding) features.push('Custom Branding');
    if (pkg.has_advanced_ai) features.push('Advanced AI');
    
    return features;
  };

  const getPrice = (pkg: ServicePackage, billingCycle: BillingCycle) => {
    return billingCycle === BillingCycle.YEARLY ? pkg.price_yearly : pkg.price_monthly;
  };

  const getSavings = (pkg: ServicePackage) => {
    if (pkg.price_yearly === 0) return 0;
    const monthlyTotal = pkg.price_monthly * 12;
    const yearlyPrice = pkg.price_yearly;
    return Math.round(((monthlyTotal - yearlyPrice) / monthlyTotal) * 100);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          Choose Your Plan
        </h2>
        <p className="text-lg text-gray-600">
          Select the perfect plan for your business needs
        </p>
      </div>

      {/* Billing Cycle Toggle */}
      <div className="flex justify-center mb-8">
        <div className="bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => onPackageSelect(selectedPackage, BillingCycle.MONTHLY)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              selectedBillingCycle === BillingCycle.MONTHLY
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => onPackageSelect(selectedPackage, BillingCycle.YEARLY)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              selectedBillingCycle === BillingCycle.YEARLY
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Yearly
            {selectedBillingCycle === BillingCycle.YEARLY && (
              <span className="ml-1 text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                Save up to 20%
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Package Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {packages.map((pkg) => {
          const isSelected = pkg.package_type === selectedPackage;
          const price = getPrice(pkg, selectedBillingCycle);
          const savings = getSavings(pkg);
          const features = getPackageFeatures(pkg);
          
          return (
            <div
              key={pkg.id}
              className={`relative bg-white rounded-lg shadow-lg border-2 transition-all duration-200 ${
                isSelected
                  ? 'border-blue-500 ring-2 ring-blue-200'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {/* Popular Badge */}
              {pkg.package_type === PackageType.PLUS && (
                <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                  <span className="bg-blue-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="p-6">
                {/* Package Header */}
                <div className="text-center mb-6">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    {pkg.name}
                  </h3>
                  <p className="text-gray-600 text-sm mb-4">
                    {pkg.description}
                  </p>
                  
                  {/* Price */}
                  <div className="mb-4">
                    <span className="text-4xl font-bold text-gray-900">
                      ${price}
                    </span>
                    <span className="text-gray-600 ml-1">
                      /{selectedBillingCycle === BillingCycle.YEARLY ? 'year' : 'month'}
                    </span>
                    {savings > 0 && selectedBillingCycle === BillingCycle.YEARLY && (
                      <div className="text-sm text-green-600 font-medium">
                        Save {savings}%
                      </div>
                    )}
                  </div>
                </div>

                {/* Features */}
                <div className="mb-6">
                  <h4 className="font-semibold text-gray-900 mb-3">What's included:</h4>
                  <ul className="space-y-2">
                    <li className="flex items-center text-sm text-gray-600">
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {pkg.max_messages_per_month.toLocaleString()} messages/month
                    </li>
                    <li className="flex items-center text-sm text-gray-600">
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {pkg.max_customers.toLocaleString()} customers
                    </li>
                    <li className="flex items-center text-sm text-gray-600">
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {pkg.max_agents} agent{pkg.max_agents > 1 ? 's' : ''}
                    </li>
                    <li className="flex items-center text-sm text-gray-600">
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {pkg.max_storage_gb}GB storage
                    </li>
                    
                    {features.map((feature, index) => (
                      <li key={index} className="flex items-center text-sm text-gray-600">
                        <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Select Button */}
                <button
                  onClick={() => onPackageSelect(pkg.package_type, selectedBillingCycle)}
                  className={`w-full py-2 px-4 rounded-md font-medium transition-colors ${
                    isSelected
                      ? 'bg-blue-600 text-white'
                      : pkg.package_type === PackageType.FREE
                      ? 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {isSelected ? 'Selected' : pkg.package_type === PackageType.FREE ? 'Get Started' : 'Choose Plan'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Additional Info */}
      <div className="mt-8 text-center text-sm text-gray-600">
        <p>
          All plans include 14-day free trial. No credit card required for Free plan.
        </p>
        <p className="mt-1">
          Need help choosing? <a href="/contact" className="text-blue-600 hover:text-blue-500">Contact our sales team</a>
        </p>
      </div>
    </div>
  );
};

export default PackageSelector;
