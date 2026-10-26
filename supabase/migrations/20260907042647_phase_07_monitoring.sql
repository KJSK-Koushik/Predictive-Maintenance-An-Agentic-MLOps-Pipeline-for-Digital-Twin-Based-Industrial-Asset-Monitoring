-- Phase 7 stores only private, bounded monitoring and challenger-governance
-- evidence. These tables grant no training, registry, alias, or deployment
-- authority and remain outside the Supabase Data API.

create table ops.monitoring_references (
    reference_id text primary key,
    release_id text not null
        references ops.model_releases (release_id) on delete restrict,
    feature_snapshot_id text not null
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    policy_id text not null,
    reference_contract_version text not null,
    profile_sha256 text not null,
    profile_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    row_count bigint not null,
    engine_count bigint not null,
    sampled_row_count bigint not null,
    created_at timestamptz not null default now(),
    constraint monitoring_references_ids_check check (
        reference_id ~ '^[0-9a-f]{64}$'
        and policy_id ~ '^[0-9a-f]{64}$'
        and profile_sha256 ~ '^[0-9a-f]{64}$'
    ),
    constraint monitoring_references_contract_check
        check (reference_contract_version = 'fd001-monitor-reference-v1'),
    constraint monitoring_references_counts_check check (
        row_count > 0 and engine_count > 0
        and sampled_row_count > 0 and sampled_row_count <= row_count
    ),
    constraint monitoring_references_object_unique unique (profile_object_id)
);

create table ops.monitoring_windows (
    window_id text primary key,
    release_id text not null
        references ops.model_releases (release_id) on delete restrict,
    reference_id text not null
        references ops.monitoring_references (reference_id) on delete restrict,
    policy_id text not null,
    feature_snapshot_id text not null,
    source_partition text not null,
    membership_sha256 text not null,
    row_count bigint not null,
    engine_count bigint not null,
    replay_sequence bigint not null,
    window_contract_version text not null,
    created_at timestamptz not null default now(),
    constraint monitoring_windows_ids_check check (
        window_id ~ '^[0-9a-f]{64}$'
        and policy_id ~ '^[0-9a-f]{64}$'
        and feature_snapshot_id ~ '^[0-9a-f]{64}$'
        and membership_sha256 ~ '^[0-9a-f]{64}$'
    ),
    constraint monitoring_windows_partition_check
        check (source_partition in ('train', 'validation', 'test', 'synthetic')),
    constraint monitoring_windows_counts_check
        check (row_count > 0 and engine_count > 0 and replay_sequence > 0),
    constraint monitoring_windows_contract_check
        check (window_contract_version = 'fd001-monitoring-window-v1'),
    constraint monitoring_windows_membership_unique unique (
        release_id, reference_id, policy_id, source_partition,
        membership_sha256, replay_sequence
    )
);

create table ops.monitoring_reports (
    report_id text primary key,
    window_id text not null
        references ops.monitoring_windows (window_id) on delete restrict,
    parent_report_id text
        references ops.monitoring_reports (report_id) on delete restrict,
    label_snapshot_id text,
    report_contract_version text not null,
    report_sha256 text not null,
    report_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    data_quality_status text not null,
    feature_shift_status text not null,
    prediction_shift_status text not null,
    service_status text not null,
    performance_status text not null,
    created_at timestamptz not null default now(),
    constraint monitoring_reports_ids_check check (
        report_id ~ '^[0-9a-f]{64}$'
        and report_sha256 ~ '^[0-9a-f]{64}$'
        and (label_snapshot_id is null or label_snapshot_id ~ '^[0-9a-f]{64}$')
    ),
    constraint monitoring_reports_contract_check
        check (report_contract_version = 'fd001-monitor-report-v1'),
    constraint monitoring_reports_status_check check (
        data_quality_status in (
            'pass', 'warning', 'alert', 'insufficient_data', 'unavailable', 'invalid'
        )
        and feature_shift_status in (
            'pass', 'warning', 'alert', 'insufficient_data', 'unavailable', 'invalid'
        )
        and prediction_shift_status in (
            'pass', 'warning', 'alert', 'insufficient_data', 'unavailable', 'invalid'
        )
        and service_status in (
            'pass', 'warning', 'alert', 'insufficient_data', 'unavailable', 'invalid'
        )
        and performance_status in (
            'pass', 'warning', 'alert', 'insufficient_data', 'unavailable', 'invalid'
        )
    ),
    constraint monitoring_reports_attachment_check check (
        (parent_report_id is null and label_snapshot_id is null)
        or (parent_report_id is not null and label_snapshot_id is not null)
    ),
    constraint monitoring_reports_no_self_parent_check
        check (parent_report_id is null or parent_report_id <> report_id),
    constraint monitoring_reports_object_unique unique (report_object_id)
);

create table ops.monitoring_alerts (
    alert_id text primary key,
    report_id text not null
        references ops.monitoring_reports (report_id) on delete restrict,
    category text not null,
    reason_codes jsonb not null,
    created_at timestamptz not null default now(),
    constraint monitoring_alerts_id_check
        check (alert_id ~ '^[0-9a-f]{64}$'),
    constraint monitoring_alerts_category_check
        check (category in ('data_quality', 'service', 'distribution_shift')),
    constraint monitoring_alerts_reasons_check check (
        jsonb_typeof(reason_codes) = 'array'
        and jsonb_array_length(reason_codes) between 1 and 50
    )
);

create table ops.retraining_candidate_requests (
    request_id text primary key,
    release_id text not null
        references ops.model_releases (release_id) on delete restrict,
    policy_id text not null,
    requested_task text not null,
    data_cutoff_window_id text not null
        references ops.monitoring_windows (window_id) on delete restrict,
    evidence_report_ids jsonb not null,
    reason text not null,
    authority text not null,
    trigger_contract_version text not null,
    created_at timestamptz not null default now(),
    constraint retraining_candidate_requests_ids_check check (
        request_id ~ '^[0-9a-f]{64}$' and policy_id ~ '^[0-9a-f]{64}$'
    ),
    constraint retraining_candidate_requests_task_check
        check (requested_task in ('regression', 'classification', 'both')),
    constraint retraining_candidate_requests_evidence_check check (
        jsonb_typeof(evidence_report_ids) = 'array'
        and jsonb_array_length(evidence_report_ids) between 1 and 20
    ),
    constraint retraining_candidate_requests_reason_check
        check (reason in ('persistent_shift', 'performance_degradation')),
    constraint retraining_candidate_requests_authority_check
        check (authority = 'evaluation_only'),
    constraint retraining_candidate_requests_contract_check
        check (trigger_contract_version = 'fd001-retraining-trigger-v1')
);

create table ops.challenger_evaluations (
    evaluation_id text primary key,
    request_id text not null
        references ops.retraining_candidate_requests (request_id) on delete restrict,
    champion_release_id text not null
        references ops.model_releases (release_id) on delete restrict,
    challenger_artifact_sha256 text,
    outcome text not null,
    checks_json jsonb not null,
    evaluation_sha256 text not null,
    evaluation_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    source_partition text not null,
    promotion_authority text not null,
    evaluation_contract_version text not null,
    created_at timestamptz not null default now(),
    constraint challenger_evaluations_ids_check check (
        evaluation_id ~ '^[0-9a-f]{64}$'
        and evaluation_sha256 ~ '^[0-9a-f]{64}$'
        and (
            challenger_artifact_sha256 is null
            or challenger_artifact_sha256 ~ '^[0-9a-f]{64}$'
        )
    ),
    constraint challenger_evaluations_outcome_check check (
        outcome in (
            'eligible_for_human_review', 'retain_champion', 'no_change',
            'blocked_no_new_training_data'
        )
    ),
    constraint challenger_evaluations_checks_check
        check (jsonb_typeof(checks_json) = 'object'),
    constraint challenger_evaluations_partition_check
        check (source_partition in ('train', 'validation', 'synthetic', 'none')),
    constraint challenger_evaluations_authority_check
        check (promotion_authority = 'none'),
    constraint challenger_evaluations_contract_check
        check (evaluation_contract_version = 'fd001-challenger-evaluation-v1'),
    constraint challenger_evaluations_object_unique unique (evaluation_object_id)
);

create index monitoring_references_release_idx
    on ops.monitoring_references (release_id, created_at desc);
create index monitoring_references_feature_snapshot_idx
    on ops.monitoring_references (feature_snapshot_id);
create index monitoring_windows_release_idx
    on ops.monitoring_windows (release_id, replay_sequence desc);
create index monitoring_windows_reference_idx
    on ops.monitoring_windows (reference_id);
create index monitoring_reports_window_idx
    on ops.monitoring_reports (window_id, created_at desc);
create index monitoring_reports_parent_idx
    on ops.monitoring_reports (parent_report_id)
    where parent_report_id is not null;
create index monitoring_alerts_report_idx
    on ops.monitoring_alerts (report_id, created_at desc);
create index retraining_candidate_release_idx
    on ops.retraining_candidate_requests (release_id, created_at desc);
create index retraining_candidate_cutoff_idx
    on ops.retraining_candidate_requests (data_cutoff_window_id);
create index challenger_evaluations_request_idx
    on ops.challenger_evaluations (request_id, created_at desc);
create index challenger_evaluations_champion_idx
    on ops.challenger_evaluations (champion_release_id);

alter table ops.monitoring_references enable row level security;
alter table ops.monitoring_windows enable row level security;
alter table ops.monitoring_reports enable row level security;
alter table ops.monitoring_alerts enable row level security;
alter table ops.retraining_candidate_requests enable row level security;
alter table ops.challenger_evaluations enable row level security;

create policy monitoring_references_runtime_select
    on ops.monitoring_references for select
    to predictive_maintenance_runtime using (true);
create policy monitoring_references_runtime_insert
    on ops.monitoring_references for insert
    to predictive_maintenance_runtime with check (true);
create policy monitoring_windows_runtime_select
    on ops.monitoring_windows for select
    to predictive_maintenance_runtime using (true);
create policy monitoring_windows_runtime_insert
    on ops.monitoring_windows for insert
    to predictive_maintenance_runtime with check (true);
create policy monitoring_reports_runtime_select
    on ops.monitoring_reports for select
    to predictive_maintenance_runtime using (true);
create policy monitoring_reports_runtime_insert
    on ops.monitoring_reports for insert
    to predictive_maintenance_runtime with check (true);
create policy monitoring_alerts_runtime_select
    on ops.monitoring_alerts for select
    to predictive_maintenance_runtime using (true);
create policy monitoring_alerts_runtime_insert
    on ops.monitoring_alerts for insert
    to predictive_maintenance_runtime with check (true);
create policy retraining_candidate_requests_runtime_select
    on ops.retraining_candidate_requests for select
    to predictive_maintenance_runtime using (true);
create policy retraining_candidate_requests_runtime_insert
    on ops.retraining_candidate_requests for insert
    to predictive_maintenance_runtime with check (authority = 'evaluation_only');
create policy challenger_evaluations_runtime_select
    on ops.challenger_evaluations for select
    to predictive_maintenance_runtime using (true);
create policy challenger_evaluations_runtime_insert
    on ops.challenger_evaluations for insert
    to predictive_maintenance_runtime with check (promotion_authority = 'none');

grant select, insert on ops.monitoring_references
    to predictive_maintenance_runtime;
grant select, insert on ops.monitoring_windows
    to predictive_maintenance_runtime;
grant select, insert on ops.monitoring_reports
    to predictive_maintenance_runtime;
grant select, insert on ops.monitoring_alerts
    to predictive_maintenance_runtime;
grant select, insert on ops.retraining_candidate_requests
    to predictive_maintenance_runtime;
grant select, insert on ops.challenger_evaluations
    to predictive_maintenance_runtime;

revoke all on ops.monitoring_references from public, anon, authenticated;
revoke all on ops.monitoring_windows from public, anon, authenticated;
revoke all on ops.monitoring_reports from public, anon, authenticated;
revoke all on ops.monitoring_alerts from public, anon, authenticated;
revoke all on ops.retraining_candidate_requests from public, anon, authenticated;
revoke all on ops.challenger_evaluations from public, anon, authenticated;
