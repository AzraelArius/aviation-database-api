-- Additional integrity rules derived from the original group project's SQL.
-- Applied transactionally by scripts/database.py after 001_initial.sql.
-- Existing invalid data causes this entire installation to roll back.
LOCK TABLE aviao, assento, voo, venda, bilhete IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM bilhete b JOIN voo v ON v.id = b.voo_id
        GROUP BY v.id, v.no_serie, b.prim_classe
        HAVING COUNT(*) > (SELECT COUNT(*) FROM assento a
            WHERE a.no_serie = v.no_serie AND a.prim_classe = b.prim_classe)
    ) THEN
        RAISE EXCEPTION 'Existing tickets exceed flight/class capacity; installation aborted without changing data';
    END IF;
    IF EXISTS (
        SELECT 1 FROM bilhete b JOIN voo v ON v.id = b.voo_id JOIN venda s USING (codigo_reserva)
        LEFT JOIN assento a ON (a.lugar, a.no_serie) = (b.lugar, b.no_serie)
        WHERE s.hora >= v.hora_partida OR
          (b.lugar IS NOT NULL AND (b.no_serie IS DISTINCT FROM v.no_serie OR a.prim_classe IS DISTINCT FROM b.prim_classe))
    ) THEN
        RAISE EXCEPTION 'Existing tickets violate sale time or seat integrity; installation aborted';
    END IF;
END $$;

ALTER TABLE voo
    ALTER COLUMN no_serie SET NOT NULL,
    ALTER COLUMN hora_partida SET NOT NULL,
    ALTER COLUMN hora_chegada SET NOT NULL,
    ALTER COLUMN partida SET NOT NULL,
    ALTER COLUMN chegada SET NOT NULL;
ALTER TABLE venda ALTER COLUMN hora SET NOT NULL,
    ADD CONSTRAINT venda_nif_format CHECK (nif_cliente ~ '^[0-9]{9}$');
ALTER TABLE bilhete
    ALTER COLUMN voo_id SET NOT NULL,
    ALTER COLUMN codigo_reserva SET NOT NULL,
    ALTER COLUMN nome_passegeiro SET NOT NULL,
    ADD CONSTRAINT bilhete_name_nonempty CHECK (length(btrim(nome_passegeiro)) > 0 AND nome_passegeiro !~ '[[:cntrl:]]'),
    ADD CONSTRAINT bilhete_price_nonnegative CHECK (preco >= 0 AND preco <> 'NaN'::numeric),
    ADD CONSTRAINT bilhete_seat_pair CHECK ((lugar IS NULL) = (no_serie IS NULL)),
    ADD CONSTRAINT bilhete_unique_flight_seat UNIQUE (voo_id, lugar);
CREATE INDEX bilhete_flight_class ON bilhete (voo_id, prim_classe);
CREATE INDEX voo_route_departure ON voo (partida, chegada, hora_partida);

-- Freeze aircraft layouts once scheduled, avoiding races between ticket writes and
-- capacity edits. Updating the parent row also forces a serialization failure for
-- stale REPEATABLE READ/SERIALIZABLE writers, rather than trusting an old snapshot.
CREATE OR REPLACE FUNCTION guard_seat_layout() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    aircraft text;
BEGIN
    FOR aircraft IN SELECT DISTINCT x FROM unnest(ARRAY[
        CASE WHEN TG_OP <> 'INSERT' THEN OLD.no_serie END,
        CASE WHEN TG_OP <> 'DELETE' THEN NEW.no_serie END]) x WHERE x IS NOT NULL ORDER BY x
    LOOP
        UPDATE aviao SET modelo = modelo WHERE no_serie = aircraft;
        IF EXISTS (SELECT 1 FROM voo WHERE no_serie = aircraft) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', CONSTRAINT = 'scheduled_aircraft_layout',
                MESSAGE = 'Cannot change the seat layout of a scheduled aircraft';
        END IF;
    END LOOP;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guard_seat_layout BEFORE INSERT OR UPDATE OR DELETE ON assento
    FOR EACH ROW EXECUTE FUNCTION guard_seat_layout();

CREATE OR REPLACE FUNCTION guard_flight() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Ticket integrity trigger deliberately takes a write lock using a no-op update.
    IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN RETURN NEW; END IF;
    UPDATE aviao SET modelo = modelo WHERE no_serie = NEW.no_serie;
    IF TG_OP = 'UPDATE' AND EXISTS (SELECT 1 FROM bilhete WHERE voo_id = OLD.id) AND
       (NEW.no_serie, NEW.hora_partida) IS DISTINCT FROM (OLD.no_serie, OLD.hora_partida) THEN
        RAISE EXCEPTION USING ERRCODE = '23514', CONSTRAINT = 'reserved_flight_immutable',
            MESSAGE = 'Cannot change aircraft or departure of a flight with tickets';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guard_flight BEFORE INSERT OR UPDATE ON voo
    FOR EACH ROW EXECUTE FUNCTION guard_flight();

CREATE OR REPLACE FUNCTION guard_sale() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.hora IS DISTINCT FROM OLD.hora AND EXISTS (
        SELECT 1 FROM bilhete WHERE codigo_reserva = OLD.codigo_reserva
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514', CONSTRAINT = 'ticketed_sale_time_immutable',
            MESSAGE = 'Cannot change the time of a sale with tickets';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guard_sale BEFORE UPDATE ON venda FOR EACH ROW EXECUTE FUNCTION guard_sale();

CREATE OR REPLACE FUNCTION enforce_ticket_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    flight_record voo%ROWTYPE;
    sale_time timestamp;
    seat_class boolean;
    capacity integer;
    sold integer;
    flight_id integer;
BEGIN
    -- Deterministic order for ticket moves; writes across workers share these locks.
    -- Actual parent writes make stale higher-isolation snapshots fail safely.
    FOR flight_id IN SELECT DISTINCT x FROM unnest(ARRAY[NEW.voo_id,
        CASE WHEN TG_OP = 'UPDATE' THEN OLD.voo_id END]) x WHERE x IS NOT NULL ORDER BY x
    LOOP
        UPDATE voo SET no_serie = no_serie WHERE id = flight_id;
    END LOOP;
    SELECT * INTO STRICT flight_record FROM voo WHERE id = NEW.voo_id;
    UPDATE venda SET hora = hora WHERE codigo_reserva = NEW.codigo_reserva RETURNING hora INTO sale_time;
    IF sale_time IS NULL OR sale_time >= flight_record.hora_partida THEN
        RAISE EXCEPTION USING ERRCODE = '23514', CONSTRAINT = 'ticket_sale_before_departure',
            MESSAGE = 'Sale must precede flight departure';
    END IF;
    IF NEW.lugar IS NOT NULL THEN
        SELECT prim_classe INTO seat_class FROM assento
            WHERE lugar = NEW.lugar AND no_serie = NEW.no_serie;
        IF NEW.no_serie IS DISTINCT FROM flight_record.no_serie OR seat_class IS DISTINCT FROM NEW.prim_classe THEN
            RAISE EXCEPTION USING ERRCODE = '23514', CONSTRAINT = 'ticket_seat_matches_flight_class',
                MESSAGE = 'Seat must match the flight aircraft and ticket class';
        END IF;
    END IF;
    SELECT COUNT(*) INTO capacity FROM assento
        WHERE no_serie = flight_record.no_serie AND prim_classe = NEW.prim_classe;
    SELECT COUNT(*) INTO sold FROM bilhete WHERE voo_id = NEW.voo_id AND prim_classe = NEW.prim_classe
        AND (TG_OP <> 'UPDATE' OR id <> OLD.id);
    IF sold >= capacity THEN
        RAISE EXCEPTION USING ERRCODE = '23514', CONSTRAINT = 'ticket_class_capacity',
            MESSAGE = 'Flight class capacity exceeded';
    END IF;
    RETURN NEW;
EXCEPTION WHEN NO_DATA_FOUND THEN
    RAISE EXCEPTION USING ERRCODE = '23503', MESSAGE = 'Flight does not exist';
END $$;
-- Replace notebook-era rules if they were manually installed.
DROP TRIGGER IF EXISTS trg_ri1_checkin ON bilhete;
DROP TRIGGER IF EXISTS trg_ri2_limite_bilhetes ON bilhete;
DROP TRIGGER IF EXISTS trg_ri3_hora_venda ON bilhete;
CREATE TRIGGER enforce_ticket_integrity BEFORE INSERT OR UPDATE ON bilhete
    FOR EACH ROW EXECUTE FUNCTION enforce_ticket_integrity();
