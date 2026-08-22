-- Phase 6 release governance extends only the private operational schema.
-- Registry state remains in MLflow; these rows are append-only decisions and
-- deployment evidence for the staging research prototype.

create table ops.model_releases (
    release_id text primary key,
    approval_request_id text not null unique,
    release_contract_version text not null,
    manifest_sha256 text not null,
    manifest_json jsonb not null,
    feature_snapshot_id text not null
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    regression_registered_name text not null,
    regression_model_version bigint not null,
    regression_source_run_id text not null,
    classification_registered_name text not null,
    classification_model_version bigint not null,
    classification_source_run_id text not null,
    previous_release_id text
        references ops.model_releases (release_id) on delete restrict,
    created_at timestamptz not null default now(),
    constraint model_releases_release_id_check
        check (release_id ~ '^[0-9a-f]{64}$'),
    constraint model_releases_approval_request_id_check
        check (approval_request_id ~ '^[0-9a-f]{64}$'),
    constraint model_releases_manifest_sha256_check
        check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    constraint model_releases_manifest_json_check
        check (
            jsonb_typeof(manifest_json) = 'object'
            and manifest_json ->> 'release_id' = release_id
            and manifest_json ->> 'approval_request_id' = approval_request_id
        ),
    constraint model_releases_contract_check
        check (release_contract_version = 'fd001-two-model-release-v1'),
    constraint model_releases_regression_name_check
        check (regression_registered_name = 'fd001-rul-regression'),
    constraint model_releases_classification_name_check
        check (
            classification_registered_name =
                'fd001-failure-risk-classification'
        ),
    constraint model_releases_versions_check
        check (
            regression_model_version > 0
            and classification_model_version > 0
        ),
    constraint model_releases_source_runs_check
        check (
            length(regression_source_run_id) between 1 and 100
            and length(classification_source_run_id) between 1 and 100
        ),
    constraint model_releases_no_self_parent_check
        check (previous_release_id is null or previous_release_id <> release_id)
);

create table ops.release_decisions (
    decision_id bigint generated always as identity primary key,
    approval_request_id text not null unique,
    release_id text not null
        references ops.model_releases (release_id) on delete restrict,
    decision text not null,
    actor text not null,
    reason text not null,
    evidence_sha256 text not null,
    decided_at timestamptz not null,
    expires_at timestamptz not null,
    created_at timestamptz not null default now(),
    constraint release_decisions_approval_request_id_check
        check (approval_request_id ~ '^[0-9a-f]{64}$'),
    constraint release_decisions_decision_check
        check (decision in ('approved', 'rejected')),
    constraint release_decisions_actor_check
        check (length(actor) between 1 and 100),
    constraint release_decisions_reason_check
        check (length(reason) between 1 and 500),
    constraint release_decisions_evidence_sha256_check
        check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    constraint release_decisions_timestamp_check
        check (expires_at > decided_at and created_at >= decided_at - interval '5 minutes'),
    constraint release_decisions_request_release_unique
        unique (approval_request_id, release_id)
);

create table ops.deployment_events (
    deployment_event_id bigint generated always as identity primary key,
    release_id text not null
        references ops.model_releases (release_id) on delete restrict,
    previous_release_id text
        references ops.model_releases (release_id) on delete restrict,
    environment text not null,
    event_type text not null,
    actor text not null,
    reason text not null,
    evidence_sha256 text not null,
    occurred_at timestamptz not null,
    created_at timestamptz not null default now(),
    constraint deployment_events_environment_check
        check (environment = 'staging'),
    constraint deployment_events_type_check
        check (
            event_type in (
                'deploy_started',
                'deploy_succeeded',
                'deploy_failed',
                'rollback_started',
                'rollback_succeeded',
                'rollback_failed'
            )
        ),
    constraint deployment_events_actor_check
        check (length(actor) between 1 and 100),
    constraint deployment_events_reason_check
        check (length(reason) between 1 and 500),
    constraint deployment_events_evidence_sha256_check
        check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    constraint deployment_events_timestamp_check
        check (created_at >= occurred_at - interval '5 minutes'),
    constraint deployment_events_previous_check
        check (previous_release_id is null or previous_release_id <> release_id)
);

create index model_releases_feature_snapshot_idx
    on ops.model_releases (feature_snapshot_id);
create index model_releases_previous_idx
    on ops.model_releases (previous_release_id)
    where previous_release_id is not null;
create index release_decisions_release_decided_idx
    on ops.release_decisions (release_id, decided_at desc);
create index deployment_events_release_occurred_idx
    on ops.deployment_events (release_id, occurred_at desc);
create index deployment_events_previous_idx
    on ops.deployment_events (previous_release_id)
    where previous_release_id is not null;

alter table ops.model_releases enable row level security;
alter table ops.release_decisions enable row level security;
alter table ops.deployment_events enable row level security;

create policy model_releases_runtime_select
    on ops.model_releases for select
    to predictive_maintenance_runtime
    using (true);
create policy model_releases_runtime_insert
    on ops.model_releases for insert
    to predictive_maintenance_runtime
    with check (true);

create policy release_decisions_runtime_select
    on ops.release_decisions for select
    to predictive_maintenance_runtime
    using (true);
create policy release_decisions_runtime_insert
    on ops.release_decisions for insert
    to predictive_maintenance_runtime
    with check (true);

create policy deployment_events_runtime_select
    on ops.deployment_events for select
    to predictive_maintenance_runtime
    using (true);
create policy deployment_events_runtime_insert
    on ops.deployment_events for insert
    to predictive_maintenance_runtime
    with check (true);

grant select, insert on ops.model_releases
    to predictive_maintenance_runtime;
grant select, insert on ops.release_decisions
    to predictive_maintenance_runtime;
grant usage on sequence ops.release_decisions_decision_id_seq
    to predictive_maintenance_runtime;
grant select, insert on ops.deployment_events
    to predictive_maintenance_runtime;
grant usage on sequence ops.deployment_events_deployment_event_id_seq
    to predictive_maintenance_runtime;

revoke all on ops.model_releases from public, anon, authenticated;
revoke all on ops.release_decisions from public, anon, authenticated;
revoke all on ops.deployment_events from public, anon, authenticated;
revoke all on sequence ops.release_decisions_decision_id_seq
    from public, anon, authenticated;
revoke all on sequence ops.deployment_events_deployment_event_id_seq
    from public, anon, authenticated;
