-- Migration 007: Terminverwaltung
-- Termine mit Kundendaten, Zeitblockierung, User-spezifische Kalender

SET search_path TO public;

CREATE TABLE IF NOT EXISTS public.appointments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    tenant_id     UUID REFERENCES public.tenants(id) ON DELETE SET NULL,
    title         TEXT NOT NULL,
    description   TEXT DEFAULT '',
    start_time    TIMESTAMPTZ NOT NULL,
    end_time      TIMESTAMPTZ NOT NULL,
    status        TEXT NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled', 'completed', 'cancelled', 'blocked')),
    -- Kundendaten
    customer_name    TEXT DEFAULT '',
    customer_email   TEXT DEFAULT '',
    customer_phone   TEXT DEFAULT '',
    customer_company TEXT DEFAULT '',
    customer_address TEXT DEFAULT '',
    customer_notes   TEXT DEFAULT '',
    -- Timestamps
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Constraint: end > start
    CONSTRAINT chk_appointment_times CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_appointments_user     ON public.appointments(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_appointments_tenant   ON public.appointments(tenant_id, start_time);
CREATE INDEX IF NOT EXISTS idx_appointments_time     ON public.appointments(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_appointments_status   ON public.appointments(status);

CREATE TRIGGER trg_appointments_updated_at
    BEFORE UPDATE ON public.appointments
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
