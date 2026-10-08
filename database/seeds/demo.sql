-- Synthetic demo only. Clock is fixed once by scripts/database.py seed-demo.
-- Seat layouts precede scheduling; every insert passes all integrity triggers.
INSERT INTO aeroporto(codigo,nome,cidade,pais) VALUES
('LIS','Lisbon demonstration airport','Lisbon','Portugal'),
('OPO','Porto demonstration airport','Porto','Portugal'),
('MAD','Madrid demonstration airport','Madrid','Spain'),
('CDG','Paris demonstration airport','Paris','France');
INSERT INTO aviao(no_serie,modelo) VALUES ('DEMO-A','Demonstration mixed class'),('DEMO-B','Demonstration economy');
INSERT INTO assento(lugar,no_serie,prim_classe) VALUES
('1A','DEMO-A',true),('1B','DEMO-A',true),
('2A','DEMO-A',false),('2B','DEMO-A',false),('2C','DEMO-A',false),('2D','DEMO-A',false),
('1A','DEMO-B',false),('1B','DEMO-B',false),('1C','DEMO-B',false),('1D','DEMO-B',false);
INSERT INTO voo(id,no_serie,hora_partida,hora_chegada,partida,chegada)
SELECT id,no_serie, current_setting('aviation.demo_as_of')::timestamptz AT TIME ZONE 'UTC' + departure,
    current_setting('aviation.demo_as_of')::timestamptz AT TIME ZONE 'UTC' + arrival,partida,chegada
FROM (VALUES
(1000,'DEMO-A',interval '-3 hours',interval '-2 hours','OPO','LIS'),
(1001,'DEMO-A',interval '2 hours',interval '3 hours','LIS','OPO'),
(1002,'DEMO-A',interval '6 hours',interval '7 hours','OPO','LIS'),
(1003,'DEMO-B',interval '4 hours',interval '6 hours','LIS','MAD'),
(1004,'DEMO-B',interval '8 hours',interval '10 hours','MAD','LIS')
) AS flights(id,no_serie,departure,arrival,partida,chegada);
INSERT INTO venda(codigo_reserva,nif_cliente,balcao,hora) VALUES
(1000,'123456789',NULL,(current_setting('aviation.demo_as_of')::timestamptz AT TIME ZONE 'UTC')-interval '2 days'),
(1001,'987654321',NULL,(current_setting('aviation.demo_as_of')::timestamptz AT TIME ZONE 'UTC')-interval '1 hour');
INSERT INTO bilhete(id,voo_id,codigo_reserva,nome_passegeiro,preco,prim_classe,lugar,no_serie) VALUES
(1000,1000,1000,'Historical First Demo',300.00,true,'1A','DEMO-A'),
(1001,1000,1000,'Historical Economy Demo',150.00,false,'2A','DEMO-A'),
(1002,1001,1001,'Future First Demo',300.00,true,NULL,NULL),
(1003,1001,1001,'Future Economy Demo',150.00,false,NULL,NULL);
SELECT setval(pg_get_serial_sequence('voo','id'),(SELECT MAX(id) FROM voo));
SELECT setval(pg_get_serial_sequence('venda','codigo_reserva'),(SELECT MAX(codigo_reserva) FROM venda));
SELECT setval(pg_get_serial_sequence('bilhete','id'),(SELECT MAX(id) FROM bilhete));
