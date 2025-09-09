export enum PackageType {
  FREE = 'free',
  PLUS = 'plus',
  PRO = 'pro'
}

export enum SubscriptionStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  CANCELLED = 'cancelled',
  EXPIRED = 'expired',
  TRIAL = 'trial'
}

export enum BillingCycle {
  MONTHLY = 'monthly',
  YEARLY = 'yearly'
}

export interface ServicePackage {
  id: number;
  name: string;
  package_type: PackageType;
  description?: string;
  price_monthly: number;
  price_yearly: number;
  
  // Feature limits
  max_messages_per_month: number;
  max_customers: number;
  max_agents: number;
  max_storage_gb: number;
  
  // Features
  has_analytics: boolean;
  has_file_upload: boolean;
  has_webhook_support: boolean;
  has_api_access: boolean;
  has_priority_support: boolean;
  has_custom_branding: boolean;
  has_advanced_ai: boolean;
  
  is_active: boolean;
}

export interface UserSubscription {
  id: number;
  user_id: number;
  package: ServicePackage;
  status: SubscriptionStatus;
  billing_cycle: BillingCycle;
  
  // Dates
  start_date: string;
  end_date?: string;
  trial_end_date?: string;
  cancelled_at?: string;
  
  // Usage tracking
  messages_used_this_month: number;
  customers_created: number;
  storage_used_gb: number;
  
  // Computed properties
  is_active: boolean;
  is_trial: boolean;
}

export interface UsageStats {
  messages_used_this_month: number;
  messages_limit: number;
  customers_created: number;
  customers_limit: number;
  storage_used_gb: number;
  storage_limit_gb: number;
  
  // Usage percentages
  messages_usage_percent: number;
  customers_usage_percent: number;
  storage_usage_percent: number;
  
  // Status
  is_near_limit: boolean;
  is_over_limit: boolean;
}

export interface RegistrationRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  phone?: string;
  package_type: PackageType;
  billing_cycle: BillingCycle;
}

export interface RegistrationResponse {
  user_id: number;
  email: string;
  full_name: string;
  subscription: UserSubscription;
  access_token: string;
  token_type: string;
}
