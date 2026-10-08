-- Flight statistics from the original group project, aggregated before joining.
CREATE MATERIALIZED VIEW estatisticas_voos AS
WITH tickets AS (
    SELECT voo_id,
        COUNT(*) FILTER (WHERE prim_classe) AS passageiros_1c,
        COUNT(*) FILTER (WHERE NOT prim_classe) AS passageiros_2c,
        COALESCE(SUM(preco) FILTER (WHERE prim_classe), 0) AS vendas_1c,
        COALESCE(SUM(preco) FILTER (WHERE NOT prim_classe), 0) AS vendas_2c
    FROM bilhete GROUP BY voo_id
), seats AS (
    SELECT no_serie,
        COUNT(*) FILTER (WHERE prim_classe) AS assentos_1c,
        COUNT(*) FILTER (WHERE NOT prim_classe) AS assentos_2c
    FROM assento GROUP BY no_serie
)
SELECT v.no_serie, v.hora_partida,
    ap.cidade AS cidade_partida, ap.pais AS pais_partida,
    ac.cidade AS cidade_chegada, ac.pais AS pais_chegada,
    EXTRACT(YEAR FROM v.hora_partida) AS ano,
    EXTRACT(MONTH FROM v.hora_partida) AS mes,
    EXTRACT(DAY FROM v.hora_partida) AS dia_do_mes,
    EXTRACT(DOW FROM v.hora_partida) AS dia_da_semana,
    COALESCE(t.passageiros_1c,0) AS passageiros_1c,
    COALESCE(t.passageiros_2c,0) AS passageiros_2c,
    COALESCE(s.assentos_1c,0) AS assentos_1c,
    COALESCE(s.assentos_2c,0) AS assentos_2c,
    COALESCE(t.vendas_1c,0) AS vendas_1c, COALESCE(t.vendas_2c,0) AS vendas_2c
FROM voo v JOIN aeroporto ap ON ap.codigo=v.partida
JOIN aeroporto ac ON ac.codigo=v.chegada
LEFT JOIN tickets t ON t.voo_id=v.id LEFT JOIN seats s ON s.no_serie=v.no_serie;
CREATE UNIQUE INDEX estatisticas_voos_flight ON estatisticas_voos(no_serie,hora_partida);
CREATE INDEX estatisticas_voos_departure ON estatisticas_voos(hora_partida);
-- Refresh explicitly after data changes: REFRESH MATERIALIZED VIEW CONCURRENTLY estatisticas_voos;
