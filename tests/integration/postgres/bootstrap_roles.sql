-- Plain PostgreSQL substitute for the roles Supabase creates automatically.
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
