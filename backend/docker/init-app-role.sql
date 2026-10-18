-- Dedicated non-superuser role for the app and its tests. The RLS FORCE
-- policy on app_user only means anything if the app connects as a role that
-- is NOT a superuser and does NOT have BYPASSRLS (the postgres bootstrap
-- user is a superuser and would silently skip RLS otherwise).
CREATE ROLE ledgerly_app LOGIN PASSWORD 'ledgerly_app_dev_password'
    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;

GRANT ALL PRIVILEGES ON DATABASE ledgerly TO ledgerly_app;
GRANT ALL ON SCHEMA public TO ledgerly_app;

-- Tables are created later by migrations running as the postgres bootstrap
-- role; this makes ledgerly_app's grants apply to those future tables too.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON TABLES TO ledgerly_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON SEQUENCES TO ledgerly_app;
