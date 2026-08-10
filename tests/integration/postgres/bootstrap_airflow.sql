-- Development-only Airflow metadata isolation inside the disposable container.
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'airflow') then
        create role airflow
            login
            password 'phase3-airflow-local-only'
            nosuperuser
            nocreatedb
            nocreaterole
            noinherit
            noreplication
            nobypassrls;
    end if;
end
$$;

select 'create database airflow owner airflow'
where not exists (select 1 from pg_database where datname = 'airflow')
\gexec

revoke all on database airflow from public;
grant connect, temporary on database airflow to airflow;
