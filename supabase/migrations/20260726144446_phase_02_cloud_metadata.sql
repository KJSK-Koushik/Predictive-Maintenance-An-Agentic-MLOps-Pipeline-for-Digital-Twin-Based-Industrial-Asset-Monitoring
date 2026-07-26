-- Phase 2 operational metadata is private and accessed only through a
-- least-privilege server-side runtime role.

create schema if not exists ops authorization postgres;

do $$
begin
    if not exists (
        select 1 from pg_roles where rolname = 'predictive_maintenance_runtime'
    ) then
        create role predictive_maintenance_runtime
            nologin
            nosuperuser
            nocreatedb
            nocreaterole
            noinherit
            noreplication
            nobypassrls;
    end if;
end
$$;

revoke all on schema ops from public;
revoke all on schema ops from anon;
revoke all on schema ops from authenticated;
grant usage on schema ops to predictive_maintenance_runtime;

alter default privileges for role postgres in schema ops
    revoke all on tables from public, anon, authenticated;
alter default privileges for role postgres in schema ops
    revoke all on sequences from public, anon, authenticated;
alter default privileges for role postgres in schema ops
    revoke execute on functions from public, anon, authenticated;

create table ops.data_objects (
    object_id bigint generated always as identity primary key,
    bucket_name text not null,
    object_key text not null,
    zone text not null,
    sha256 text not null,
    byte_size bigint not null,
    content_type text not null,
    verification_state text not null,
    verified_at timestamptz not null,
    created_at timestamptz not null default now(),
    constraint data_objects_bucket_name_check
        check (
            bucket_name ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'
            and bucket_name !~ '--'
        ),
    constraint data_objects_object_key_check
        check (
            length(object_key) between 1 and 1024
            and left(object_key, 1) <> '/'
            and right(object_key, 1) <> '/'
            and object_key !~ '(^|/)\.\.?(/|$)'
            and object_key !~ '//'
            and position(chr(92) in object_key) = 0
        ),
    constraint data_objects_zone_check
        check (zone in ('raw', 'derived')),
    constraint data_objects_sha256_check
        check (sha256 ~ '^[0-9a-f]{64}$'),
    constraint data_objects_byte_size_check
        check (byte_size >= 0),
    constraint data_objects_content_type_check
        check (length(content_type) between 1 and 255),
    constraint data_objects_verification_state_check
        check (verification_state = 'verified'),
    constraint data_objects_verified_at_check
        check (verified_at <= created_at + interval '5 minutes'),
    constraint data_objects_bucket_key_unique
        unique (bucket_name, object_key)
);

create table ops.dataset_snapshots (
    snapshot_id text primary key,
    dataset_family text not null,
    dataset_subset text not null,
    contract_version text not null,
    parser_version text not null,
    code_revision text not null,
    manifest_sha256 text not null,
    manifest_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    required_file_count smallint not null,
    state text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint dataset_snapshots_snapshot_id_check
        check (snapshot_id ~ '^[0-9a-f]{64}$'),
    constraint dataset_snapshots_dataset_family_check
        check (length(dataset_family) between 1 and 100),
    constraint dataset_snapshots_dataset_subset_check
        check (dataset_subset ~ '^[A-Z0-9_-]{1,32}$'),
    constraint dataset_snapshots_contract_version_check
        check (length(contract_version) between 1 and 100),
    constraint dataset_snapshots_parser_version_check
        check (length(parser_version) between 1 and 100),
    constraint dataset_snapshots_code_revision_check
        check (length(code_revision) between 1 and 100),
    constraint dataset_snapshots_manifest_sha256_check
        check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    constraint dataset_snapshots_required_file_count_check
        check (required_file_count > 0),
    constraint dataset_snapshots_state_check
        check (state in ('available', 'inconsistent')),
    constraint dataset_snapshots_timestamps_check
        check (updated_at >= created_at)
);

create table ops.snapshot_files (
    snapshot_id text not null
        references ops.dataset_snapshots (snapshot_id) on delete restrict,
    logical_filename text not null,
    file_position smallint not null,
    object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    primary key (snapshot_id, logical_filename),
    constraint snapshot_files_position_unique
        unique (snapshot_id, file_position),
    constraint snapshot_files_object_unique
        unique (snapshot_id, object_id),
    constraint snapshot_files_filename_check
        check (
            length(logical_filename) between 1 and 255
            and logical_filename !~ '[/\\]'
            and logical_filename not in ('.', '..')
        ),
    constraint snapshot_files_position_check
        check (file_position > 0)
);

create table ops.lineage_edges (
    parent_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    child_object_id bigint not null
        references ops.data_objects (object_id) on delete restrict,
    relationship_type text not null,
    created_at timestamptz not null default now(),
    primary key (parent_object_id, child_object_id, relationship_type),
    constraint lineage_edges_relationship_type_check
        check (
            relationship_type in (
                'documented_by_manifest',
                'derived_from',
                'reported_by'
            )
        ),
    constraint lineage_edges_no_self_link
        check (parent_object_id <> child_object_id)
);

create table ops.ingestion_runs (
    run_id uuid primary key,
    idempotency_key text not null unique,
    state text not null,
    started_at timestamptz not null,
    finished_at timestamptz,
    error_code text,
    error_detail text,
    constraint ingestion_runs_idempotency_key_check
        check (idempotency_key ~ '^[0-9a-f]{64}$'),
    constraint ingestion_runs_state_check
        check (state in ('started', 'available', 'failed', 'inconsistent')),
    constraint ingestion_runs_error_code_check
        check (
            error_code is null
            or error_code ~ '^[a-z][a-z0-9_.]{2,99}$'
        ),
    constraint ingestion_runs_error_detail_check
        check (error_detail is null or length(error_detail) <= 1000),
    constraint ingestion_runs_finish_check
        check (
            (state = 'started' and finished_at is null)
            or (state <> 'started' and finished_at is not null)
        ),
    constraint ingestion_runs_error_pair_check
        check (
            (state in ('failed', 'inconsistent') and error_code is not null)
            or (state in ('started', 'available') and error_code is null)
        ),
    constraint ingestion_runs_timestamps_check
        check (finished_at is null or finished_at >= started_at)
);

create index data_objects_zone_idx on ops.data_objects (zone);
create index snapshot_files_object_idx on ops.snapshot_files (object_id);
create index lineage_edges_child_idx on ops.lineage_edges (child_object_id);
create index ingestion_runs_state_idx on ops.ingestion_runs (state);

alter table ops.data_objects enable row level security;
alter table ops.dataset_snapshots enable row level security;
alter table ops.snapshot_files enable row level security;
alter table ops.lineage_edges enable row level security;
alter table ops.ingestion_runs enable row level security;

create policy data_objects_runtime_select
    on ops.data_objects for select
    to predictive_maintenance_runtime
    using (true);
create policy data_objects_runtime_insert
    on ops.data_objects for insert
    to predictive_maintenance_runtime
    with check (verification_state = 'verified');

create policy dataset_snapshots_runtime_select
    on ops.dataset_snapshots for select
    to predictive_maintenance_runtime
    using (true);
create policy dataset_snapshots_runtime_insert
    on ops.dataset_snapshots for insert
    to predictive_maintenance_runtime
    with check (state = 'available');
create policy dataset_snapshots_runtime_update
    on ops.dataset_snapshots for update
    to predictive_maintenance_runtime
    using (true)
    with check (state in ('available', 'inconsistent'));

create policy snapshot_files_runtime_select
    on ops.snapshot_files for select
    to predictive_maintenance_runtime
    using (true);
create policy snapshot_files_runtime_insert
    on ops.snapshot_files for insert
    to predictive_maintenance_runtime
    with check (true);

create policy lineage_edges_runtime_select
    on ops.lineage_edges for select
    to predictive_maintenance_runtime
    using (true);
create policy lineage_edges_runtime_insert
    on ops.lineage_edges for insert
    to predictive_maintenance_runtime
    with check (parent_object_id <> child_object_id);

create policy ingestion_runs_runtime_select
    on ops.ingestion_runs for select
    to predictive_maintenance_runtime
    using (true);
create policy ingestion_runs_runtime_insert
    on ops.ingestion_runs for insert
    to predictive_maintenance_runtime
    with check (state in ('started', 'available', 'failed'));
create policy ingestion_runs_runtime_update
    on ops.ingestion_runs for update
    to predictive_maintenance_runtime
    using (true)
    with check (state in ('started', 'available', 'failed', 'inconsistent'));

grant select, insert on ops.data_objects to predictive_maintenance_runtime;
grant usage on sequence ops.data_objects_object_id_seq
    to predictive_maintenance_runtime;
grant select, insert, update (state, updated_at)
    on ops.dataset_snapshots to predictive_maintenance_runtime;
grant select, insert on ops.snapshot_files to predictive_maintenance_runtime;
grant select, insert on ops.lineage_edges to predictive_maintenance_runtime;
grant select, insert, update (
    state,
    started_at,
    finished_at,
    error_code,
    error_detail
) on ops.ingestion_runs to predictive_maintenance_runtime;

revoke all on all tables in schema ops from public, anon, authenticated;
revoke all on all sequences in schema ops from public, anon, authenticated;
