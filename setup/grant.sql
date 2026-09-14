-- Run as the PostgreSQL superuser, connected to the wiki database:
--   sudo -u postgres psql -d <db_name> -v db_name=<db_name> -f /opt/pywiki/setup/grant.sql

ALTER DATABASE :"db_name" OWNER TO pywiki;
-- GRANT USAGE, CREATE ON SCHEMA public TO pywiki;
-- ALTER SCHEMA public OWNER TO pywiki;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA PUBLIC TO pywiki;
GRANT ALL ON ALL SEQUENCES IN SCHEMA PUBLIC TO pywiki;

