# Protocol tests (Stage 3)

Tests are written from `docs/protocol.md` and talk to a server only through a serial
link, so the same tests run against the mock now and the STM32 later.

```
pip install -r tests/requirements.txt
pytest tests/ --port mock           # built-in mock server (no board), ~2 min
pytest tests/ --port COM5           # real board; close any terminal using the port
pytest tests/ --port mock -m "not slow"   # skip the timeout tests
python tests/mutation_check.py      # inject 15 faults into the mock; each must be caught
python tests/mock_server.py --listen 5555   # standalone mock for the GUI: socket://127.0.0.1:5555
```
`--port` may also be set with env `GAME_PORT`. A `socket://host:port` URL works too.

| File | Content |
|---|---|
| `protocol_lib.py` | XOR checksum, frame builder, reply checker (shared) |
| `mock_server.py` | independent Python server of protocol v1.0 (+ fault injection) |
| `link.py` | pyserial wrapper: send, read replies (checksum verified), `sync_to_idle` |
| `test_required.py` | brief's cases + all 8 win lines for X and O |
| `test_state_table.py` | all 18 cells of the state table, next state probed without side effects |
| `test_robustness.py` | garbage, bad checksum, 32/33-byte limit, timeouts, bursts, no unsolicited replies |

Caveats: on the board the 500 ms timeout tests need a real UART delay tolerance
(0.4-0.9 s window). The mock proves the tests are sound; it does not prove the firmware.
