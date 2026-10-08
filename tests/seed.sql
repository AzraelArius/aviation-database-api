-- Small synthetic fixture. Flight times are relative to the test clock.
INSERT INTO aeroporto VALUES ('LIS','Lisbon test airport','Lisbon','Portugal'),('OPO','Porto test airport','Porto','Portugal');
INSERT INTO aviao VALUES ('TEST-1','Test aircraft'),('TEST-2','Economy only');
INSERT INTO assento VALUES ('1A','TEST-1',true),('1B','TEST-1',true),('2A','TEST-1',false),('2B','TEST-1',false),('2C','TEST-1',false),('1A','TEST-2',false);
INSERT INTO voo(no_serie,hora_partida,hora_chegada,partida,chegada) VALUES
('TEST-1',CURRENT_TIMESTAMP + interval '2 hours',CURRENT_TIMESTAMP + interval '3 hours','LIS','OPO'),
('TEST-2',CURRENT_TIMESTAMP + interval '4 hours',CURRENT_TIMESTAMP + interval '5 hours','LIS','OPO');
