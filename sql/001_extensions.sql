-- Migration 001: Extensions
-- Ausführen als postgres superuser
-- Einmalig pro Datenbank

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- für Fuzzy-Search optional
CREATE EXTENSION IF NOT EXISTS unaccent;  -- für Umlaute in FTS optional
