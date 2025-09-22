-- Database initialization script
-- This script creates the initial database structure

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'app')\gexec

-- Connect to the app database
\c app;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: Tables will be created by Alembic migrations
-- This script is mainly for database creation and basic setup
