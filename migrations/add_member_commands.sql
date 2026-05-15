-- Migration: add_member_commands
-- Adds columns required by the new member-facing slash commands:
--   /catfight, /howcat, /compare, /catstatus, /send, /streak
--
-- Run once against your live database:
--   psql -U cat_bot -d cat_bot -f migrations/add_member_commands.sql
--
-- Every ALTER TABLE uses IF NOT EXISTS so it is safe to re-run.

BEGIN;

-- ── New cat types ────────────────────────────────────────────────────────────
-- These cat types were added to the bot's type_dict but were never given
-- columns in the profile table. /send and /compare read/write them directly.

ALTER TABLE public.profile
    ADD COLUMN IF NOT EXISTS "cat_Princess" bigint NOT NULL DEFAULT 0;

ALTER TABLE public.profile
    ADD COLUMN IF NOT EXISTS "cat_Rainbow"  bigint NOT NULL DEFAULT 0;

ALTER TABLE public.profile
    ADD COLUMN IF NOT EXISTS "cat_Angel"    bigint NOT NULL DEFAULT 0;

-- ── Achievement boolean for /send ────────────────────────────────────────────
-- achemb(message, "generous", "followup") is called in /send.
-- Without this column the achievement silently fails (catpg ignores unknown fields),
-- but adding it means it can be unlocked and displayed properly.

ALTER TABLE public.profile
    ADD COLUMN IF NOT EXISTS generous boolean NOT NULL DEFAULT false;

-- ── Verify ───────────────────────────────────────────────────────────────────
DO $$
DECLARE
    missing text[] := '{}';
    col text;
    cols text[] := ARRAY[
        'cat_Princess', 'cat_Rainbow', 'cat_Angel', 'generous'
    ];
BEGIN
    FOREACH col IN ARRAY cols LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'profile'
              AND column_name  = col
        ) THEN
            missing := array_append(missing, col);
        END IF;
    END LOOP;

    IF array_length(missing, 1) > 0 THEN
        RAISE EXCEPTION 'Migration incomplete — columns still missing: %', missing;
    ELSE
        RAISE NOTICE 'Migration OK — all columns present.';
    END IF;
END $$;

COMMIT;
