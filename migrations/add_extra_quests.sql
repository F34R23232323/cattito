-- Migration: Add extra quest columns to profile table
-- Run this on your existing database to enable extra quest progress tracking.
-- Safe to run multiple times (uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

ALTER TABLE profile
    ADD COLUMN IF NOT EXISTS catnip_rain_reward integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS extra1_quest character varying NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS extra1_progress integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS extra1_cooldown integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS extra1_reward integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS extra2_quest character varying NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS extra2_progress integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS extra2_cooldown integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS extra2_reward integer NOT NULL DEFAULT 0;
