import React, { useState } from 'react';
import { PackageType, BillingCycle } from '../types/subscription';

interface RegistrationFormProps {
  onRegister: (data: RegistrationData) => void;
  loading?: boolean;
}

interface RegistrationData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  companyName: string;
  phone: string;
  packageType: PackageType;
  billingCycle: BillingCycle;
}

const RegistrationForm: React.FC<RegistrationFormProps> = ({ onRegister, loading = false }) => {
  const [formData, setFormData] = useState<RegistrationData>({
    email: '',
    password: '',
    firstName: '',
    lastName: '',
    companyName: '',
    phone: '',
    packageType: PackageType.FREE,
    billingCycle: BillingCycle.MONTHLY,
  });

  const [errors, setErrors] = useState<Partial<RegistrationData>>({});

  const validateForm = (): boolean => {
    const newErrors: Partial<RegistrationData> = {};

    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email is invalid';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (!formData.firstName) {
      newErrors.firstName = 'First name is required';
    }

    if (!formData.lastName) {
      newErrors.lastName = 'Last name is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onRegister(formData);
    }
  };

  const handleInputChange = (field: keyof RegistrationData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
        Create Your Account
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Personal Information */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="firstName" className="block text-sm font-medium text-gray-700">
              First Name *
            </label>
            <input
              type="text"
              id="firstName"
              value={formData.firstName}
              onChange={(e) => handleInputChange('firstName', e.target.value)}
              className={`mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 ${
                errors.firstName ? 'border-red-500' : ''
              }`}
              placeholder="John"
            />
            {errors.firstName && (
              <p className="mt-1 text-sm text-red-600">{errors.firstName}</p>
            )}
          </div>

          <div>
            <label htmlFor="lastName" className="block text-sm font-medium text-gray-700">
              Last Name *
            </label>
            <input
              type="text"
              id="lastName"
              value={formData.lastName}
              onChange={(e) => handleInputChange('lastName', e.target.value)}
              className={`mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 ${
                errors.lastName ? 'border-red-500' : ''
              }`}
              placeholder="Doe"
            />
            {errors.lastName && (
              <p className="mt-1 text-sm text-red-600">{errors.lastName}</p>
            )}
          </div>
        </div>

        {/* Email */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700">
            Email Address *
          </label>
          <input
            type="email"
            id="email"
            value={formData.email}
            onChange={(e) => handleInputChange('email', e.target.value)}
            className={`mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 ${
              errors.email ? 'border-red-500' : ''
            }`}
            placeholder="john@example.com"
          />
          {errors.email && (
            <p className="mt-1 text-sm text-red-600">{errors.email}</p>
          )}
        </div>

        {/* Password */}
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700">
            Password *
          </label>
          <input
            type="password"
            id="password"
            value={formData.password}
            onChange={(e) => handleInputChange('password', e.target.value)}
            className={`mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 ${
              errors.password ? 'border-red-500' : ''
            }`}
            placeholder="••••••••"
          />
          {errors.password && (
            <p className="mt-1 text-sm text-red-600">{errors.password}</p>
          )}
        </div>

        {/* Company Name */}
        <div>
          <label htmlFor="companyName" className="block text-sm font-medium text-gray-700">
            Company Name
          </label>
          <input
            type="text"
            id="companyName"
            value={formData.companyName}
            onChange={(e) => handleInputChange('companyName', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            placeholder="Acme Corp"
          />
        </div>

        {/* Phone */}
        <div>
          <label htmlFor="phone" className="block text-sm font-medium text-gray-700">
            Phone Number
          </label>
          <input
            type="tel"
            id="phone"
            value={formData.phone}
            onChange={(e) => handleInputChange('phone', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            placeholder="+1 (555) 123-4567"
          />
        </div>

        {/* Package Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Choose Your Plan
          </label>
          <div className="space-y-2">
            {Object.values(PackageType).map((packageType) => (
              <label key={packageType} className="flex items-center">
                <input
                  type="radio"
                  name="packageType"
                  value={packageType}
                  checked={formData.packageType === packageType}
                  onChange={(e) => handleInputChange('packageType', e.target.value as PackageType)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                />
                <span className="ml-2 text-sm text-gray-700 capitalize">
                  {packageType} Plan
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Billing Cycle (only for paid plans) */}
        {formData.packageType !== PackageType.FREE && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Billing Cycle
            </label>
            <div className="space-y-2">
              {Object.values(BillingCycle).map((cycle) => (
                <label key={cycle} className="flex items-center">
                  <input
                    type="radio"
                    name="billingCycle"
                    value={cycle}
                    checked={formData.billingCycle === cycle}
                    onChange={(e) => handleInputChange('billingCycle', e.target.value as BillingCycle)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <span className="ml-2 text-sm text-gray-700 capitalize">
                    {cycle}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Creating Account...' : 'Create Account'}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-gray-600">
        Already have an account?{' '}
        <a href="/login" className="font-medium text-blue-600 hover:text-blue-500">
          Sign in
        </a>
      </p>
    </div>
  );
};

export default RegistrationForm;
