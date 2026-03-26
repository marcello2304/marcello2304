-- Voicebot Performance Monitoring
-- Metrics-Tabelle für Latency-Tracking
CREATE TABLE IF NOT EXISTS voicebot_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    step TEXT NOT NULL, -- 'embedding', 'rag', 'llm', 'tts', 'total'
    duration_ms INTEGER NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_session ON voicebot_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON voicebot_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_step ON voicebot_metrics(step);

-- View für schnelle Statistiken
CREATE OR REPLACE VIEW voicebot_performance_stats AS
SELECT
    step,
    COUNT(*) as total_calls,
    ROUND(AVG(duration_ms)) as avg_ms,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)) as median_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)) as p95_ms,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms)) as p99_ms,
    MIN(duration_ms) as min_ms,
    MAX(duration_ms) as max_ms
FROM voicebot_metrics
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY step
ORDER BY
    CASE step
        WHEN 'total' THEN 1
        WHEN 'llm' THEN 2
        WHEN 'rag' THEN 3
        WHEN 'embedding' THEN 4
        WHEN 'tts' THEN 5
    END;

-- Slow Query Log (>3s total time)
CREATE TABLE IF NOT EXISTS voicebot_slow_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_query TEXT,
    total_duration_ms INTEGER,
    rag_chunks TEXT,
    llm_response TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_slow_queries_timestamp ON voicebot_slow_queries(timestamp DESC);
