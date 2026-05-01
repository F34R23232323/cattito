-- ============================================================
-- Cattito Dashboard – full migration
-- Run once against your PostgreSQL database.
-- Safe to re-run (all statements use IF NOT EXISTS / IF EXISTS).
-- ============================================================

-- 1. Dashboard sessions table (if not already created)
CREATE TABLE IF NOT EXISTS public.dashboard_sessions (
    session_id      TEXT             NOT NULL PRIMARY KEY,
    user_id         BIGINT           NOT NULL,
    access_token    TEXT             NOT NULL,
    refresh_token   TEXT             NOT NULL DEFAULT '',
    created_at      DOUBLE PRECISION NOT NULL,
    expires_at      DOUBLE PRECISION NOT NULL,
    guilds          JSONB            NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_dashboard_sessions_user_id ON public.dashboard_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_dashboard_sessions_expires ON public.dashboard_sessions (expires_at);

-- 2. Add user profile columns to sessions (fixes null username/avatar in header)
ALTER TABLE public.dashboard_sessions
    ADD COLUMN IF NOT EXISTS username    TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS avatar      TEXT,
    ADD COLUMN IF NOT EXISTS global_name TEXT;

-- 3. DB-backed OAuth state table (fixes the /servers → / redirect loop)
--    State tokens are now stored in the DB so they survive server restarts.
CREATE TABLE IF NOT EXISTS public.dashboard_oauth_state (
    state      TEXT             NOT NULL PRIMARY KEY,
    expires_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oauth_state_expires ON public.dashboard_oauth_state (expires_at);