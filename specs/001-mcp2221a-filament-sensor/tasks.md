# Tasks: MCP2221A Dual Filament Sensor Monitor

**Input**: Design documents from `/specs/001-mcp2221a-filament-sensor/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- Paths shown below for single project structure per plan.md

## Phase 3.1: Setup
- [ ] T001 Create project directory structure: src/models, src/services, src/cli, src/lib/*, tests/contract, tests/integration, tests/unit
- [ ] T002 Initialize Python project with requirements.txt including EasyMCP2221, FastAPI, Textual, Pydantic, PyYAML, structlog, pytest, pytest-asyncio
- [ ] T003 [P] Configure pytest.ini with asyncio markers and test paths
- [ ] T004 [P] Create .gitignore for Python, __pycache__, *.pyc, venv/, .env
- [ ] T005 [P] Create default config.yaml with sensor pins, calibration (2.88mm), polling (100ms), API port (5002)

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (API)
- [ ] T006 [P] Contract test GET /status endpoint in tests/contract/test_status_endpoint.py - verify StatusResponse schema
- [ ] T007 [P] Contract test GET /config endpoint in tests/contract/test_config_endpoint.py - verify ConfigurationResponse schema
- [ ] T008 [P] Contract test POST /config endpoint in tests/contract/test_config_update.py - verify configuration update and validation
- [ ] T009 [P] Contract test GET /alerts endpoint in tests/contract/test_alerts_endpoint.py - verify alert filtering and response
- [ ] T010 [P] Contract test POST /alerts/{id}/acknowledge in tests/contract/test_alert_acknowledge.py - verify acknowledgment
- [ ] T011 [P] Contract test GET /metrics endpoint in tests/contract/test_metrics_endpoint.py - verify MetricsResponse schema
- [ ] T012 [P] Contract test WebSocket /ws endpoint in tests/contract/test_websocket.py - verify connection and message format

### Integration Tests (Hardware & System)
- [ ] T013 [P] Integration test MCP2221A connection in tests/integration/test_mcp2221_connection.py - detect device, configure GPIO
- [ ] T014 [P] Integration test dual sensor detection in tests/integration/test_dual_sensors.py - read both sensors simultaneously
- [ ] T015 [P] Integration test pulse counting in tests/integration/test_pulse_detection.py - verify edge detection and debouncing
- [ ] T016 [P] Integration test filament runout detection in tests/integration/test_runout_detection.py - simulate filament removal
- [ ] T017 [P] Integration test configuration persistence in tests/integration/test_config_persistence.py - YAML load/save
- [ ] T018 [P] Integration test session metrics in tests/integration/test_session_metrics.py - verify calculations and aggregation
- [ ] T019 [P] Integration test terminal UI updates in tests/integration/test_display_updates.py - verify real-time refresh

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models
- [ ] T020 [P] Create SensorReading model in src/models/sensor_reading.py with Pydantic validation
- [ ] T021 [P] Create SensorConfiguration model in src/models/sensor_configuration.py with constraints
- [ ] T022 [P] Create SessionMetrics model in src/models/session_metrics.py with calculated fields
- [ ] T023 [P] Create AlertEvent model in src/models/alert_event.py with event types and severity
- [ ] T024 [P] Create SystemStatus model in src/models/system_status.py as singleton

### Library: mcp2221_sensor
- [ ] T025 Create src/lib/mcp2221_sensor/__init__.py with MCP2221Manager class for USB connection
- [ ] T026 Add GPIO configuration methods to MCP2221Manager for pin setup and pull-ups
- [ ] T027 Implement pulse detection with debouncing in src/lib/mcp2221_sensor/pulse_detector.py
- [ ] T028 Add connection retry logic with exponential backoff to MCP2221Manager
- [ ] T029 [P] Create CLI interface src/lib/mcp2221_sensor/__main__.py with --test-connection command

### Library: display
- [ ] T030 Create src/lib/display/__init__.py with SensorMonitorApp Textual application
- [ ] T031 Implement split-screen layout in src/lib/display/layouts.py for dual sensor view
- [ ] T032 Create real-time status widgets in src/lib/display/widgets.py showing filament, movement, usage
- [ ] T033 Add alert notification panel to display critical events
- [ ] T034 [P] Create CLI interface src/lib/display/__main__.py with --demo mode

### Library: api_server
- [ ] T035 Create src/lib/api_server/__init__.py with FastAPI app initialization
- [ ] T036 Implement GET /status endpoint returning sensor states and usage
- [ ] T037 Implement GET /config endpoint returning current configuration
- [ ] T038 Implement POST /config endpoint with validation for pin conflicts
- [ ] T039 Implement GET /alerts endpoint with severity and sensor_id filters
- [ ] T040 Implement POST /alerts/{id}/acknowledge endpoint
- [ ] T041 Implement GET /metrics endpoint returning session statistics
- [ ] T042 Implement WebSocket /ws endpoint for real-time updates
- [ ] T043 [P] Create CLI interface src/lib/api_server/__main__.py with --port option

### Library: config
- [ ] T044 [P] Create src/lib/config/__init__.py with ConfigManager using Pydantic and YAML
- [ ] T045 [P] Implement configuration validation checking pin conflicts and ranges
- [ ] T046 [P] Add hot-reload capability monitoring config.yaml changes
- [ ] T047 [P] Create CLI interface src/lib/config/__main__.py with --validate and --export commands

### Core Services
- [ ] T048 Create src/services/sensor_monitor.py with SensorMonitor class for polling loop
- [ ] T049 Implement filament presence detection reading runout GPIO pins
- [ ] T050 Implement movement detection with 5-second timeout
- [ ] T051 Add pulse counting with distance calculation using calibration factor
- [ ] T052 Create src/services/data_aggregator.py for metrics calculation
- [ ] T053 Implement alert generation for runout and reconnection events
- [ ] T054 Add SQLite session storage in src/services/session_storage.py

### Main Application
- [ ] T055 Create src/cli/main.py orchestrating all components
- [ ] T056 Implement command-line argument parsing (--config, --debug, --no-api, --demo)
- [ ] T057 Add graceful shutdown handling for Ctrl+C
- [ ] T058 Implement keyboard shortcuts (q=quit, r=reset, 1/2=toggle sensors)

## Phase 3.4: Integration
- [ ] T059 Connect SensorMonitor to MCP2221Manager for hardware polling
- [ ] T060 Wire data flow from sensors to display widgets via queue
- [ ] T061 Connect API endpoints to live sensor data
- [ ] T062 Implement WebSocket broadcasting for real-time updates
- [ ] T063 Add structured logging with structlog throughout application
- [ ] T064 Implement error recovery for USB disconnection/reconnection

## Phase 3.5: Polish
- [ ] T065 [P] Unit tests for pulse detection algorithm in tests/unit/test_pulse_algorithm.py
- [ ] T066 [P] Unit tests for calibration calculations in tests/unit/test_calibration.py
- [ ] T067 [P] Unit tests for configuration validation in tests/unit/test_config_validation.py
- [ ] T068 [P] Performance test: verify <10ms UI update latency
- [ ] T069 [P] Performance test: verify <5ms API response time
- [ ] T070 [P] Memory test: verify <50MB usage for 24-hour session
- [ ] T071 [P] Create user documentation in docs/user_guide.md
- [ ] T072 [P] Create API documentation in docs/api_reference.md
- [ ] T073 Run quickstart.md validation scenarios end-to-end
- [ ] T074 Package application with setup.py for pip installation

## Dependencies
- Setup (T001-T005) must complete first
- All tests (T006-T019) before implementation (T020-T058)
- Models (T020-T024) before services that use them
- Libraries (T025-T047) before main application (T055-T058)
- Core implementation before integration (T059-T064)
- Everything before polish (T065-T074)

## Parallel Execution Examples

### Batch 1: Contract Tests (after setup)
```bash
# Launch T006-T012 together:
Task: "Contract test GET /status endpoint in tests/contract/test_status_endpoint.py"
Task: "Contract test GET /config endpoint in tests/contract/test_config_endpoint.py"
Task: "Contract test POST /config endpoint in tests/contract/test_config_update.py"
Task: "Contract test GET /alerts endpoint in tests/contract/test_alerts_endpoint.py"
Task: "Contract test POST /alerts/{id}/acknowledge in tests/contract/test_alert_acknowledge.py"
Task: "Contract test GET /metrics endpoint in tests/contract/test_metrics_endpoint.py"
Task: "Contract test WebSocket /ws endpoint in tests/contract/test_websocket.py"
```

### Batch 2: Integration Tests (after setup)
```bash
# Launch T013-T019 together:
Task: "Integration test MCP2221A connection in tests/integration/test_mcp2221_connection.py"
Task: "Integration test dual sensor detection in tests/integration/test_dual_sensors.py"
Task: "Integration test pulse counting in tests/integration/test_pulse_detection.py"
Task: "Integration test filament runout detection in tests/integration/test_runout_detection.py"
Task: "Integration test configuration persistence in tests/integration/test_config_persistence.py"
Task: "Integration test session metrics in tests/integration/test_session_metrics.py"
Task: "Integration test terminal UI updates in tests/integration/test_display_updates.py"
```

### Batch 3: Data Models (after tests)
```bash
# Launch T020-T024 together:
Task: "Create SensorReading model in src/models/sensor_reading.py"
Task: "Create SensorConfiguration model in src/models/sensor_configuration.py"
Task: "Create SessionMetrics model in src/models/session_metrics.py"
Task: "Create AlertEvent model in src/models/alert_event.py"
Task: "Create SystemStatus model in src/models/system_status.py"
```

### Batch 4: Unit Tests (during polish)
```bash
# Launch T065-T067 together:
Task: "Unit tests for pulse detection algorithm in tests/unit/test_pulse_algorithm.py"
Task: "Unit tests for calibration calculations in tests/unit/test_calibration.py"
Task: "Unit tests for configuration validation in tests/unit/test_config_validation.py"
```

## Notes
- [P] tasks = different files, no shared dependencies
- Verify ALL tests fail before implementing (TDD requirement)
- Commit after each task with descriptive message
- Run tests continuously during implementation
- Use --demo mode for development without hardware

## Validation Checklist
*GATE: Verified before execution*

- [x] All contracts have corresponding tests (T006-T012)
- [x] All entities have model tasks (T020-T024)
- [x] All tests come before implementation
- [x] Parallel tasks are truly independent
- [x] Each task specifies exact file path
- [x] No parallel task modifies same file as another

## Estimated Timeline
- Setup: 30 minutes
- Tests: 2 hours (must fail first)
- Core Implementation: 4 hours
- Integration: 1 hour
- Polish: 2 hours
- **Total**: ~9-10 hours of focused development