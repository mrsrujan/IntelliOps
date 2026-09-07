"""
Prompt construction for the RCA task.

We use one prompt across all providers (Bedrock, OpenAI, Gemini). Per-provider
tuning is a future refinement — for the current scope, this prompt is deliberately
straightforward and lets each model shape its own response style.
"""


def build_prompt(anomaly: dict, context: dict) -> str:
    return f"""You are an SRE assistant analysing a production incident. Produce a concise, actionable root-cause analysis based only on the evidence provided.

## Anomaly Detected
- Service      : {anomaly['service']}
- Type         : {anomaly['anomaly_type']}
- Metric       : {anomaly.get('metric') or 'n/a'}
- Value        : {anomaly.get('value')}
- Threshold    : {anomaly.get('threshold')}
- Detected at  : {anomaly['timestamp']}

## Recent Errors (last {context['time_window_minutes']} minutes)
{_format_logs(context.get('recent_errors', []))}

## Similar Past Incidents (last 7 days, same service)
{_format_incidents(context.get('similar_incidents', []))}

## Task
Respond in this exact format:

**Root cause**: 1–2 sentences on the most likely cause.
**Blast radius**: what else is impacted or at risk (1 sentence).
**Recommended action**: the single most useful next step (e.g. rollback, scale-up, restart pods).
**Confidence**: high / medium / low, with one line explaining why.

Keep the whole response under 200 words. Do not restate the input.
"""


def _format_logs(logs: list) -> str:
    if not logs:
        return "(no WARN/ERROR entries in window — anomaly may be metric-driven only)"
    return "\n".join(
        f"[{log.get('timestamp', '?')}] {log.get('level', '?')}: {log.get('message', '')[:200]}"
        for log in logs[:15]
    )


def _format_incidents(incidents: list) -> str:
    if not incidents:
        return "(none — this appears to be a novel pattern for this service)"
    return "\n".join(
        f"- {inc['timestamp'][:19]} · {inc.get('anomaly_type')} · resolved={inc.get('resolution_status')} · summary: {inc.get('rca_summary', '')[:150]}"
        for inc in incidents
    )
