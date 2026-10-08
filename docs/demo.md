# Five-minute terminal demonstration

Use a fresh demo database. Schedules are relative to the recorded first-load UTC
clock; an old persistent volume may contain historical flights. Do not reset a
volume containing wanted data. Follow [setup.md](setup.md) to start the services.

1. Run `docker compose ps -a`: PostgreSQL should be healthy, the initializer should
   have exited with code 0, and the API should be running.
2. Run `curl -s http://localhost:8080/` and `curl -s http://localhost:8080/voos/LIS/`.
3. Buy the final available first-class seat on flight 1001:

   ```bash
   curl -i -X POST http://localhost:8080/compra/1001/ \
     -H 'Content-Type: application/json' \
     -d '{"nif_cliente":"123456789","bilhetes":[["Demo Passenger",true]]}'
   ```

   Expect HTTP 201 with a reservation and ticket ID. On a fresh database the ticket
   is 1004. Use the actual returned ID in the next command.
4. Run `curl -i -X PUT http://localhost:8080/checkin/1004/` twice. Both responses
   should show the same seat; on an untouched demo it is `1A` on `DEMO-A`.
5. Repeat a first-class purchase on flight 1001. Expect HTTP 409, not an extra sale.
6. Run `docker compose run --rm init python scripts/database.py bootstrap`.
   It should report up-to-date migrations and an already loaded demo, preserving
   the purchase and seat assignment.
7. Run the [integration tests](testing.md) and show the real coverage report.

Useful optional terminal captures: a successful purchase/check-in pair, a rejected
capacity request, healthy service/startup output, and a real pytest/coverage result.
Do not fabricate screenshots, CI success badges or performance figures. None are
generated or committed here. Production deployment and a frontend are not part of
the demonstration.
