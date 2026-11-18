# Graph Report - graph-src  (2026-11-16)

## Corpus Check
- 85 files · ~42,844 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: .css 1)

## Summary
- 827 nodes · 2580 edges · 37 communities (24 shown, 13 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 297 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Detections.tsx
- Ioc
- auth.py
- main.py
- AuditLog
- normalization.py
- suricata.py
- api.ts
- MispClient
- ingest_raw
- schemas/ioc.py
- pipeline.py
- IocStatus
- abusech.py
- dashboard_stats
- pages.test.tsx
- CollectorError
- models/ioc.py
- App.tsx
- integrations_status.py
- Topbar.tsx
- MemoryStorage
- misp_ops.py
- Settings
- BaseCollector
- system_health
- RawIndicator
- auth.tsx
- OtxCollector
- app_core_config

## God Nodes (most connected - your core abstractions)
1. `Ioc` - 43 edges
2. `AuditLog` - 36 edges
3. `useApi()` - 31 edges
4. `fmtRelative()` - 29 edges
5. `Detections()` - 29 edges
6. `RawIndicator` - 28 edges
7. `Principal` - 27 edges
8. `AsyncBlock()` - 26 edges
9. `fmtNum()` - 26 edges
10. `IocDetail()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `_audit()` --uses--> `AuditLog`  [INFERRED]
  backend_app/api/auth.py → backend_app/models/ioc.py
- `bootstrap_admin()` --uses--> `AuditLog`  [INFERRED]
  backend_app/api/auth.py → backend_app/models/ioc.py
- `list_audit()` --uses--> `AuditLog`  [INFERRED]
  backend_app/api/dashboard.py → backend_app/models/ioc.py
- `audit_actions()` --uses--> `AuditLog`  [INFERRED]
  backend_app/api/dashboard.py → backend_app/models/ioc.py
- `workflows_summary()` --uses--> `AuditLog`  [INFERRED]
  backend_app/api/dashboard.py → backend_app/models/ioc.py

## Import Cycles
- None detected.

## Communities (37 total, 13 thin omitted)

### Community 0 - "Detections.tsx"
Cohesion: 0.08
Nodes (113): BarList(), ChartTooltip(), Donut(), legendStyle, ScoreHistogram(), ScoreLine(), TimelineChart(), TimelinePoint (+105 more)

### Community 1 - "Ioc"
Cohesion: 0.06
Nodes (25): _detection_out(), DetectionReview, get_integrations(), global_search(), ioc_activity(), _iso(), lifecycle_funnel(), list_detections() (+17 more)

### Community 2 - "auth.py"
Cohesion: 0.09
Nodes (28): _audit(), bootstrap_admin(), create_user(), _ensure_other_admin(), list_users(), login(), LoginRequest, logout() (+20 more)

### Community 3 - "main.py"
Cohesion: 0.06
Nodes (7): health(), ready(), RateLimitMiddleware, SecurityHeadersMiddleware, SlidingWindowLimiter, create_app(), lifespan()

### Community 4 - "AuditLog"
Cohesion: 0.12
Nodes (16): collect_run(), enrich_run(), expire_run(), generate_daily_report(), get_daily_report(), ingest_sensor_alerts(), _ms(), normalize_run() (+8 more)

### Community 5 - "normalization.py"
Cohesion: 0.09
Nodes (19): IocType, Component, compute_score(), _detection_score(), _enrichment_score(), _freshness_half_life(), _freshness_score(), _independent_sources_score() (+11 more)

### Community 7 - "suricata.py"
Cohesion: 0.10
Nodes (8): get_logger(), JsonFormatter, setup_logging(), parse_eve(), SuricataAlert, trackable_value(), parse_alerts_json(), WazuhAlert

### Community 8 - "api.ts"
Cohesion: 0.10
Nodes (23): ApiError, DailyReport, DetectionItem, FunnelStage, get(), IntegrationItem, Ioc, IocActivity (+15 more)

### Community 10 - "ingest_raw"
Cohesion: 0.18
Nodes (9): _audit(), _declared_type(), _expires_at(), _handle_existing(), ingest_raw(), IngestOutcome, _link_source(), _merge_tags() (+1 more)

### Community 11 - "schemas/ioc.py"
Cohesion: 0.15
Nodes (13): ingest(), run_scoring(), DashboardStats, IngestItem, IngestRequest, IngestResponse, IngestResult, IocDetail (+5 more)

### Community 12 - "pipeline.py"
Cohesion: 0.18
Nodes (7): _active_policy_params(), _best_reliability(), expire_due_iocs(), _independent_source_count(), run_full_pipeline(), score_and_decide(), StageReport

### Community 13 - "IocStatus"
Cohesion: 0.19
Nodes (11): lifecycle_events(), manual_transition(), can_transition(), LifecycleError, risk_level_for(), transition(), TransitionResult, IocStatus (+3 more)

### Community 14 - "abusech.py"
Cohesion: 0.19
Nodes (4): _AbuseChCollector, _parse_time(), ThreatFoxCollector, UrlhausCollector

### Community 15 - "dashboard_stats"
Cohesion: 0.16
Nodes (10): dashboard_stats(), get_ioc(), _independent_count(), _ioc_filters(), list_iocs(), source_stats(), IocSource, IocListResponse (+2 more)

### Community 16 - "pages.test.tsx"
Cohesion: 0.18
Nodes (8): ToastProvider(), DashboardStats, AuthProvider(), mocked, signedIn(), stats, me(), renderAt()

### Community 17 - "CollectorError"
Cohesion: 0.20
Nodes (5): CollectorError, BlocklistDeCollector, FeodoCollector, _parse_time(), UrlscanCollector

### Community 18 - "models/ioc.py"
Cohesion: 0.16
Nodes (8): Base, Enrichment, IntelSource, RiskLevel, ScoreHistory, ScoringPolicy, SourceKind, _uuid()

### Community 19 - "App.tsx"
Cohesion: 0.24
Nodes (15): App(), Audit, Automation, Detections, Health, IocDetail, Lifecycle, Login (+7 more)

### Community 20 - "integrations_status.py"
Cohesion: 0.35
Nodes (8): _collectors(), _enrichment(), integrations_status(), _iso(), _last_audit(), _misp(), _n8n(), _sensor()

### Community 21 - "Topbar.tsx"
Cohesion: 0.33
Nodes (10): AppShell(), BrandMark(), Sidebar(), Breadcrumbs(), Notifications(), Topbar(), UserMenu(), usePopover() (+2 more)

### Community 23 - "misp_ops.py"
Cohesion: 0.24
Nodes (5): Publication, active_misp_publication(), build_client(), publish_pending_to_misp(), revoke_misp_attribute()

### Community 26 - "system_health"
Cohesion: 0.29
Nodes (4): audit_actions(), list_audit(), system_health(), workflows_summary()

### Community 27 - "RawIndicator"
Cohesion: 0.22
Nodes (4): MalwareBazaarCollector, RawIndicator, _entries(), SyntheticCollector

### Community 28 - "auth.tsx"
Cohesion: 0.24
Nodes (9): NAV_GROUPS, NavItem, ROUTE_LABELS, Me, Role, tokenStore, AuthContext, AuthState (+1 more)

## Knowledge Gaps
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Ioc` connect `Ioc` to `AuditLog`, `MispClient`, `ingest_raw`, `schemas/ioc.py`, `pipeline.py`, `IocStatus`, `dashboard_stats`, `models/ioc.py`, `misp_ops.py`, `system_health`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `Ioc` (e.g. with `system_health()` and `dashboard_stats()`) actually correct?**
  _`Ioc` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Should `Detections.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.07695749440715884 - nodes in this community are weakly interconnected._
- **Why does `AuditLog` connect `AuditLog` to `Ioc`, `auth.py`, `ingest_raw`, `schemas/ioc.py`, `pipeline.py`, `IocStatus`, `dashboard_stats`, `models/ioc.py`, `integrations_status.py`, `misp_ops.py`, `system_health`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `AuditLog` (e.g. with `_audit()` and `bootstrap_admin()`) actually correct?**
  _`AuditLog` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Should `Ioc` be split into smaller, more focused modules?**
  _Cohesion score 0.062004662004662 - nodes in this community are weakly interconnected._
- **Why does `RawIndicator` connect `RawIndicator` to `AuditLog`, `ingest_raw`, `schemas/ioc.py`, `pipeline.py`, `abusech.py`, `CollectorError`, `BaseCollector`, `OtxCollector`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._