-- Phase 3 derived metadata extends the private operational schema. Airflow
-- metadata remains in its own database and is never written to ops.

create table ops.derived_snapshots (
    derived_snapshot_id text primary key,
    source_snapshot_id text not null
        references ops.dataset_snapshots (snapshot_id) on delete restrict,
    parent_derived_snapshot_id text
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    artifact_kind text not null,
    contract_version text not null,
    transformation_version text not null,
    serializer_version text not null,
    code_revision text not null,
    manifest_sha256 text not null,
    manifest_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    required_file_count smallint not null,
    state text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint derived_snapshots_id_check
        check (derived_snapshot_id ~ '^[0-9a-f]{64}$'),
    constraint derived_snapshots_artifact_kind_check
        check (artifact_kind in ('processed', 'feature', 'quality_report')),
    constraint derived_snapshots_parent_check
        check (
            (artifact_kind = 'processed' and parent_derived_snapshot_id is null)
            or (artifact_kind in ('feature', 'quality_report')
                and parent_derived_snapshot_id is not null)
        ),
    constraint derived_snapshots_contract_version_check
        check (length(contract_version) between 1 and 100),
    constraint derived_snapshots_transformation_version_check
        check (length(transformation_version) between 1 and 100),
    constraint derived_snapshots_serializer_version_check
        check (length(serializer_version) between 1 and 100),
    constraint derived_snapshots_code_revision_check
        check (length(code_revision) between 1 and 100),
    constraint derived_snapshots_manifest_sha256_check
        check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    constraint derived_snapshots_required_file_count_check
        check (required_file_count > 0),
    constraint derived_snapshots_state_check
        check (state in ('available', 'inconsistent')),
    constraint derived_snapshots_timestamps_check
        check (updated_at >= created_at),
    constraint derived_snapshots_manifest_unique
        unique (manifest_object_id)
);

create table ops.derived_snapshot_files (
    derived_snapshot_id text not null
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    logical_filename text not null,
    file_position smallint not null,
    object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    schema_json jsonb not null,
    column_roles jsonb not null,
    primary key (derived_snapshot_id, logical_filename),
    constraint derived_snapshot_files_position_unique
        unique (derived_snapshot_id, file_position),
    constraint derived_snapshot_files_object_unique
        unique (derived_snapshot_id, object_id),
    constraint derived_snapshot_files_filename_check
        check (
            length(logical_filename) between 1 and 255
            and logical_filename !~ '[/\\]'
            and logical_filename not in ('.', '..')
        ),
    constraint derived_snapshot_files_position_check
        check (file_position > 0),
    constraint derived_snapshot_files_schema_check
        check (jsonb_typeof(schema_json) = 'array'),
    constraint derived_snapshot_files_roles_check
        check (jsonb_typeof(column_roles) = 'object')
);

create table ops.transformation_runs (
    run_id uuid primary key,
    idempotency_key text not null unique,
    source_snapshot_id text not null
        references ops.dataset_snapshots (snapshot_id) on delete restrict,
    pipeline_version text not null,
    code_revision text not null,
    state text not null,
    processed_snapshot_id text
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    feature_snapshot_id text
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    quality_snapshot_id text
        references ops.derived_snapshots (derived_snapshot_id) on delete restrict,
    started_at timestamptz not null,
    finished_at timestamptz,
    error_code text,
    error_detail text,
    constraint transformation_runs_idempotency_key_check
        check (idempotency_key ~ '^[0-9a-f]{64}$'),
    constraint transformation_runs_pipeline_version_check
        check (length(pipeline_version) between 1 and 100),
    constraint transformation_runs_code_revision_check
        check (length(code_revision) between 1 and 100),
    constraint transformation_runs_state_check
        check (state in ('started', 'available', 'failed', 'inconsistent')),
    constraint transformation_runs_error_code_check
        check (error_code is null or error_code ~ '^[a-z][a-z0-9_.]{2,99}$'),
    constraint transformation_runs_error_detail_check
        check (error_detail is null or length(error_detail) <= 1000),
    constraint transformation_runs_finish_check
        check (
            (state = 'started' and finished_at is null)
            or (state <> 'started' and finished_at is not null)
        ),
    constraint transformation_runs_outputs_check
        check (
            (state = 'available'
                and processed_snapshot_id is not null
                and feature_snapshot_id is not null
                and quality_snapshot_id is not null)
            or (state <> 'available')
        ),
    constraint transformation_runs_error_pair_check
        check (
            (state in ('failed', 'inconsistent') and error_code is not null)
            or (state in ('started', 'available') and error_code is null)
        ),
    constraint transformation_runs_timestamps_check
        check (finished_at is null or finished_at >= started_at)
);

create index derived_snapshots_source_kind_idx
    on ops.derived_snapshots (source_snapshot_id, artifact_kind);
create index derived_snapshots_parent_idx
    on ops.derived_snapshots (parent_derived_snapshot_id)
    where parent_derived_snapshot_id is not null;
create index derived_snapshot_files_object_idx
    on ops.derived_snapshot_files (object_id);
create index transformation_runs_source_idx
    on ops.transformation_runs (source_snapshot_id, state);
create index transformation_runs_processed_idx
    on ops.transformation_runs (processed_snapshot_id)
    where processed_snapshot_id is not null;
create index transformation_runs_feature_idx
    on ops.transformation_runs (feature_snapshot_id)
    where feature_snapshot_id is not null;
create index transformation_runs_quality_idx
    on ops.transformation_runs (quality_snapshot_id)
    where quality_snapshot_id is not null;

alter table ops.derived_snapshots enable row level security;
alter table ops.derived_snapshot_files enable row level security;
alter table ops.transformation_runs enable row level security;

create policy derived_snapshots_runtime_select
    on ops.derived_snapshots for select
    to predictive_maintenance_runtime
    using (true);
create policy derived_snapshots_runtime_insert
    on ops.derived_snapshots for insert
    to predictive_maintenance_runtime
    with check (state = 'available');
create policy derived_snapshots_runtime_mark_inconsistent
    on ops.derived_snapshots for update
    to predictive_maintenance_runtime
    using (state = 'available')
    with check (state = 'inconsistent');

create policy derived_snapshot_files_runtime_select
    on ops.derived_snapshot_files for select
    to predictive_maintenance_runtime
    using (true);
create policy derived_snapshot_files_runtime_insert
    on ops.derived_snapshot_files for insert
    to predictive_maintenance_runtime
    with check (true);

create policy transformation_runs_runtime_select
    on ops.transformation_runs for select
    to predictive_maintenance_runtime
    using (true);
create policy transformation_runs_runtime_insert
    on ops.transformation_runs for insert
    to predictive_maintenance_runtime
    with check (state in ('started', 'failed'));
create policy transformation_runs_runtime_update
    on ops.transformation_runs for update
    to predictive_maintenance_runtime
    using (state in ('started', 'failed'))
    with check (state in ('started', 'available', 'failed', 'inconsistent'));
create policy transformation_runs_runtime_mark_inconsistent
    on ops.transformation_runs for update
    to predictive_maintenance_runtime
    using (state = 'available')
    with check (state = 'inconsistent');

grant select, insert, update (state, updated_at)
    on ops.derived_snapshots to predictive_maintenance_runtime;
grant select, insert
    on ops.derived_snapshot_files to predictive_maintenance_runtime;
grant select, insert, update (
    state,
    processed_snapshot_id,
    feature_snapshot_id,
    quality_snapshot_id,
    started_at,
    finished_at,
    error_code,
    error_detail
) on ops.transformation_runs to predictive_maintenance_runtime;

revoke all on ops.derived_snapshots from public, anon, authenticated;
revoke all on ops.derived_snapshot_files from public, anon, authenticated;
revoke all on ops.transformation_runs from public, anon, authenticated;
