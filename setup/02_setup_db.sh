#!/bin/sh


psql <<'SQL'
CREATE USER pywiki WITH PASSWORD 'Some-Complex-Password';
CREATE DATABASE pywiki OWNER pywiki;
GRANT ALL PRIVILEGES ON DATABASE pywiki TO pywiki;
SQL
