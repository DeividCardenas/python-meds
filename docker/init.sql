-- init.sql
-- Executed automatically by the PostgreSQL container on first start.
-- Creates the two logical databases and grants full privileges to genhospi_admin.

-- 1. Create the catalog database (INVIMA CUM static data)
CREATE DATABASE genhospi_catalog
    WITH OWNER = genhospi_admin
         ENCODING = 'UTF8'
         LC_COLLATE = 'en_US.utf8'
         LC_CTYPE = 'en_US.utf8'
         TEMPLATE = template0;

-- 2. Create the pricing database (supplier Excel uploads & cost processing)
CREATE DATABASE genhospi_pricing
    WITH OWNER = genhospi_admin
         ENCODING = 'UTF8'
         LC_COLLATE = 'en_US.utf8'
         LC_CTYPE = 'en_US.utf8'
         TEMPLATE = template0;

-- 3. Grant all privileges on both databases to genhospi_admin
GRANT ALL PRIVILEGES ON DATABASE genhospi_catalog TO genhospi_admin;
GRANT ALL PRIVILEGES ON DATABASE genhospi_pricing TO genhospi_admin;
