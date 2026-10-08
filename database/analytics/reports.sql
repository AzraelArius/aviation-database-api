-- Original analytics rewritten with explicit rolling periods and tie handling.
-- Last twelve months, excluding future departures; opposite directions share a route.
WITH demand AS (
    SELECT LEAST(cidade_partida,cidade_chegada) AS cidade_a,
        GREATEST(cidade_partida,cidade_chegada) AS cidade_b,
        AVG((passageiros_1c+passageiros_2c)::numeric / NULLIF(assentos_1c+assentos_2c,0)) AS preenchimento_medio
    FROM estatisticas_voos
    WHERE hora_partida >= CURRENT_TIMESTAMP - INTERVAL '1 year' AND hora_partida < CURRENT_TIMESTAMP
    GROUP BY 1,2
)
SELECT * FROM demand WHERE preenchimento_medio = (SELECT MAX(preenchimento_medio) FROM demand)
ORDER BY cidade_a,cidade_b;

-- Fleet coverage in the last three months. The view represents scheduled aircraft
-- only; aircraft with no flights cannot be counted using this view alone.
SELECT LEAST(cidade_partida,cidade_chegada) AS cidade_a,
    GREATEST(cidade_partida,cidade_chegada) AS cidade_b
FROM estatisticas_voos
WHERE hora_partida >= CURRENT_TIMESTAMP - INTERVAL '3 months' AND hora_partida < CURRENT_TIMESTAMP
GROUP BY 1,2
HAVING COUNT(DISTINCT no_serie) = (SELECT COUNT(DISTINCT no_serie) FROM estatisticas_voos)
ORDER BY cidade_a,cidade_b;

-- Sales revenue (not profit): joint departure/arrival geography and calendar time.
-- GROUPING masks distinguish subtotal NULLs from missing values.
SELECT pais_partida,pais_chegada,cidade_partida,cidade_chegada,ano,mes,dia_do_mes,
    GROUPING(pais_partida,pais_chegada,cidade_partida,cidade_chegada) AS geography_level,
    GROUPING(ano,mes,dia_do_mes) AS time_level,
    SUM(vendas_1c) AS vendas_1c,SUM(vendas_2c) AS vendas_2c,
    SUM(vendas_1c+vendas_2c) AS vendas_total
FROM estatisticas_voos
GROUP BY ROLLUP((pais_partida,pais_chegada),(cidade_partida,cidade_chegada)), ROLLUP(ano,mes,dia_do_mes)
ORDER BY geography_level,time_level,pais_partida,pais_chegada,cidade_partida,cidade_chegada,ano,mes,dia_do_mes;

-- Weekly class ratio with global, country-pair and city-pair summaries.
SELECT pais_partida,pais_chegada,cidade_partida,cidade_chegada,dia_da_semana,
    GROUPING(pais_partida,pais_chegada,cidade_partida,cidade_chegada) AS geography_level,
    SUM(passageiros_1c) AS total_1c,SUM(passageiros_2c) AS total_2c,
    SUM(passageiros_1c)::numeric / NULLIF(SUM(passageiros_2c),0) AS ratio_1c_2c
FROM estatisticas_voos
GROUP BY dia_da_semana,ROLLUP((pais_partida,pais_chegada),(cidade_partida,cidade_chegada))
ORDER BY geography_level,pais_partida,pais_chegada,cidade_partida,cidade_chegada,dia_da_semana;
