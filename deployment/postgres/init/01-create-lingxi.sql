SELECT 'CREATE DATABASE lingxi'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'lingxi')\gexec
