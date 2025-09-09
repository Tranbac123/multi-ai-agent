import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RegistrationForm from '../components/RegistrationForm';
import PackageSelector from '../components/PackageSelector';
import { PackageType, BillingCycle, RegistrationRequest } from '../types/subscription';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<'package' | 'form'>('package');
  const [selectedPackage, setSelectedPackage] = useState<PackageType>(PackageType.FREE);
  const [selectedBillingCycle, setSelectedBillingCycle] = useState<BillingCycle>(BillingCycle.MONTHLY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePackageSelect = (packageType: PackageType, billingCycle: BillingCycle) => {
    setSelectedPackage(packageType);
    setSelectedBillingCycle(billingCycle);
  };

  const handleNext = () => {
    setStep('form');
  };

  const handleBack = () => {
    setStep('package');
  };

  const handleRegister = async (formData: RegistrationRequest) => {
    setLoading(true);
    setError(null);

    try {
      const registrationData = {
        ...formData,
        package_type: selectedPackage,
        billing_cycle: selectedBillingCycle,
      };

      const response = await fetch('/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registrationData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
      }

      const result = await response.json();
      
      // Store the access token
      localStorage.setItem('access_token', result.access_token);
      localStorage.setItem('user', JSON.stringify({
        id: result.user_id,
        email: result.email,
        full_name: result.full_name,
        subscription: result.subscription,
      }));

      // Redirect to dashboard
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Get Started with AI Customer Agent
          </h1>
          <p className="text-lg text-gray-600">
            Join thousands of businesses using AI to provide exceptional customer support
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="flex justify-center mb-8">
          <div className="flex items-center space-x-4">
            <div className={`flex items-center ${step === 'package' ? 'text-blue-600' : 'text-green-600'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === 'package' ? 'bg-blue-600 text-white' : 'bg-green-600 text-white'
              }`}>
                1
              </div>
              <span className="ml-2 text-sm font-medium">Choose Plan</span>
            </div>
            
            <div className={`w-8 h-0.5 ${step === 'form' ? 'bg-green-600' : 'bg-gray-300'}`}></div>
            
            <div className={`flex items-center ${step === 'form' ? 'text-blue-600' : 'text-gray-400'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === 'form' ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'
              }`}>
                2
              </div>
              <span className="ml-2 text-sm font-medium">Create Account</span>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="max-w-md mx-auto mb-6">
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
          </div>
        )}

        {/* Content */}
        {step === 'package' ? (
          <div>
            <PackageSelector
              onPackageSelect={handlePackageSelect}
              selectedPackage={selectedPackage}
              selectedBillingCycle={selectedBillingCycle}
            />
            
            <div className="text-center mt-8">
              <button
                onClick={handleNext}
                className="bg-blue-600 text-white px-8 py-3 rounded-md font-medium hover:bg-blue-700 transition-colors"
              >
                Continue to Registration
              </button>
            </div>
          </div>
        ) : (
          <div>
            <RegistrationForm
              onRegister={handleRegister}
              loading={loading}
            />
            
            <div className="text-center mt-6">
              <button
                onClick={handleBack}
                className="text-gray-600 hover:text-gray-800 font-medium"
              >
                ← Back to Plan Selection
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-12 text-center text-sm text-gray-500">
          <p>
            By creating an account, you agree to our{' '}
            <a href="/terms" className="text-blue-600 hover:text-blue-500">Terms of Service</a>
            {' '}and{' '}
            <a href="/privacy" className="text-blue-600 hover:text-blue-500">Privacy Policy</a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
