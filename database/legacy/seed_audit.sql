-- Read-only inspection of the original generated dataset.
-- Run in a disposable database containing aviacao.sql and populate.sql.
WITH sold AS (
    SELECT voo_id, prim_classe, count(*) AS tickets FROM bilhete GROUP BY voo_id, prim_classe
), capacity AS (
    SELECT no_serie, prim_classe, count(*) AS seats FROM assento GROUP BY no_serie, prim_classe
)
SELECT v.id AS voo_id, v.no_serie, s.prim_classe, s.tickets, c.seats,
       s.tickets - c.seats AS excess
FROM sold s JOIN voo v ON v.id = s.voo_id
JOIN capacity c ON (c.no_serie, c.prim_classe) = (v.no_serie, s.prim_classe)
WHERE s.tickets > c.seats ORDER BY v.id, s.prim_classe;
