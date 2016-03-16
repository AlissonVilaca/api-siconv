
CREATE TABLE matviews (
  mv_name NAME NOT NULL PRIMARY KEY
  , v_name NAME NOT NULL
  , last_refresh TIMESTAMP WITH TIME ZONE
);

CREATE LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION create_matview(name, name)
RETURNS void AS
$BODY$
    DECLARE
        matview ALIAS FOR $1;
        view_name ALIAS FOR $2;
        entry matviews%ROWTYPE;
    BEGIN
        SELECT * INTO entry FROM matviews WHERE mv_name = quote_ident(matview);
        IF FOUND THEN
            RAISE EXCEPTION 'Materialized view ''%'' already exists.', quote_ident(matview);
        END IF;

        EXECUTE 'REVOKE ALL ON ' || quote_ident(view_name) || ' FROM PUBLIC';
        EXECUTE 'GRANT SELECT ON ' || quote_ident(view_name) || ' TO PUBLIC';
        EXECUTE 'CREATE TABLE ' || quote_ident(matview) || ' AS SELECT * FROM ' || quote_ident(view_name);
        EXECUTE 'REVOKE ALL ON ' || quote_ident(matview) || ' FROM PUBLIC';
        EXECUTE 'GRANT SELECT ON ' || quote_ident(matview) || ' TO PUBLIC';

        INSERT INTO matviews (mv_name, v_name, last_refresh)
        VALUES (quote_ident(matview), quote_ident(view_name), CURRENT_TIMESTAMP);
        RETURN;
    END
$BODY$
LANGUAGE "plpgsql" VOLATILE SECURITY DEFINER
COST 100;


CREATE OR REPLACE FUNCTION drop_matview(name)
RETURNS void AS
$BODY$
    DECLARE
        matview ALIAS FOR $1;
        entry matviews%ROWTYPE;
    BEGIN
        SELECT * INTO entry FROM matviews WHERE mv_name = quote_ident(matview);
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Materialized view % does not exist.', quote_ident(matview);
        END IF;

        EXECUTE 'DROP TABLE ' || quote_ident(matview);
        DELETE FROM matviews WHERE mv_name=quote_ident(matview);
        RETURN;
    END
$BODY$
LANGUAGE 'plpgsql' VOLATILE SECURITY DEFINER
COST 100;


CREATE OR REPLACE FUNCTION refresh_matview(name)
RETURNS void AS
$BODY$
    DECLARE
        matview ALIAS FOR $1;
        entry matviews%ROWTYPE;
    BEGIN
        SELECT * INTO entry FROM matviews WHERE mv_name = quote_ident(matview);
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Materialized view % does not exist.', quote_ident(matview);
        END IF;
        EXECUTE 'DELETE FROM ' || quote_ident(matview);
        EXECUTE 'INSERT INTO ' || quote_ident(matview) || ' SELECT * FROM ' || entry.v_name;
        UPDATE matviews
        SET last_refresh=CURRENT_TIMESTAMP
        WHERE mv_name=quote_ident(matview);
        RETURN;
    END
$BODY$
LANGUAGE 'plpgsql' VOLATILE SECURITY DEFINER
COST 100;