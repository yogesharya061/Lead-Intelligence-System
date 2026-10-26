"""Versioned, deterministic four-factor qualification policy."""
from datetime import date

FIELDS = ('name', 'company', 'company_size', 'industry', 'source', 'last_interaction_date')
CORE = {'saas', 'software', 'enterprise software', 'analytics', 'ai/ml', 'cybersecurity', 'fintech', 'healthtech', 'hr tech', 'insurtech', 'edtech'}
ADJACENT = {'finance', 'healthcare', 'insurance', 'logistics', 'supply chain', 'manufacturing', 'retail', 'consulting', 'marketing', 'business services', 'telecom'}
OTHER = {'agriculture', 'automotive', 'biotech', 'climate tech', 'construction', 'consumer', 'consumer services', 'cryptocurrency', 'cultural', 'education', 'energy', 'entertainment', 'environmental', 'events', 'government', 'hospitality', 'legal', 'media', 'nonprofit', 'pharmaceuticals', 'real estate', 'services', 'sports', 'trade', 'travel'}
SOURCES = {'inbound demo request': 2, 'referral': 2, 'sales call': 1, 'webinar attendee': 1, 'content download': 0, 'linkedin outreach': 0}


def clean(value):
    value = (value or '').strip()
    return '' if value.casefold() in {'na', 'n/a', 'null', 'none'} else value


def score_lead(raw, row_number, as_of):
    lead = {k: clean(raw.get(k)) for k in FIELDS}
    flags = [f'missing_{k}' for k, v in lead.items() if not v]
    try:
        size = int(lead['company_size'])
        if size < 1:
            raise ValueError()
    except ValueError:
        size = None
        flags.append('invalid_company_size')
    try:
        days = (as_of - date.fromisoformat(lead['last_interaction_date'])).days
        if days < 0:
            flags.append('future_interaction_date')
    except ValueError:
        days = None
        flags.append('invalid_interaction_date')
    industry, source = lead['industry'].casefold(), lead['source'].casefold()
    if industry not in CORE | ADJACENT | OTHER:
        flags.append('unmapped_industry')
    if source not in SOURCES:
        flags.append('unmapped_source')
    points = {
        'company_size': 3 if size and 50 <= size <= 2000 else 1 if size and (10 <= size < 50 or 2000 < size <= 5000) else 0,
        'industry_fit': 3 if industry in CORE else 2 if industry in ADJACENT else 0,
        'engagement_source': SOURCES.get(source, 0),
        'recency': 2 if days is not None and 0 <= days <= 30 else 1 if days is not None and 30 < days <= 90 else 0,
    }
    score = max(1, sum(points.values()))
    reasons = [f'{k}={v}' for k, v in points.items()]
    rejection = []
    if size and size < 10:
        rejection.append('below_minimum_company_size')
    if days is not None and days > 365:
        rejection.append('interaction_older_than_365_days')
    if flags:
        decision = 'review'
    elif rejection:
        decision = 'rejected'
    else:
        decision = 'qualified' if score >= 7 else 'review' if score >= 5 else 'rejected'
        if decision == 'rejected':
            rejection.append('score_below_5')
    return dict(lead_id=f'L{row_number:04d}', input_row=row_number + 1, lead=lead,
                score=score, factor_scores=points, days_since_interaction=days,
                rule_decision=decision, decision=decision, flags=sorted(set(flags)),
                rejection_reasons=rejection if decision == 'rejected' else [],
                reasoning='; '.join(reasons + rejection + flags),
                priority=None, priority_rank=None, outreach=None, sequence=[])
