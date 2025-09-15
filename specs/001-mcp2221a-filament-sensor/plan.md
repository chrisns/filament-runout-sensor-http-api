# Implementation Plan: MCP2221A Dual Filament Sensor Monitor

**Branch**: `001-mcp2221a-filament-sensor` | **Date**: 2025-09-15 | **Spec**: [link](spec.md)
**Input**: Feature specification from `/specs/001-mcp2221a-filament-sensor/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Develop a Python-based Windows application to monitor dual BIGTREETECH filament sensors via MCP2221A USB-GPIO adapter, providing real-time terminal display with split-screen visualization, filament usage tracking with configurable calibration (2.88mm/pulse default), and HTTP JSON API on port 5002 for remote monitoring.

## Technical Context
**Language/Version**: Python 3.11
**Primary Dependencies**: EasyMCP2221 (USB-GPIO), FastAPI (HTTP server), Textual (Terminal UI)
**Storage**: SQLite for session data (in-memory)
**Testing**: pytest with asyncio support
**Target Platform**: Windows 10/11 native
**Project Type**: single - standalone monitoring application
**Performance Goals**: 100ms sensor polling, <10ms UI update latency
**Constraints**: USB connection reliability, real-time pulse detection accuracy
**Scale/Scope**: 2 sensors, session-based data, single-user local application

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 1 (single monitoring application)
- Using framework directly? Yes (EasyMCP2221, FastAPI, Textual - no wrappers)
- Single data model? Yes (sensor readings and configuration)
- Avoiding patterns? Yes (direct implementation, no unnecessary abstractions)

**Architecture**:
- EVERY feature as library? Yes - sensor, display, api, config modules
- Libraries listed:
  - `mcp2221_sensor`: Hardware interface and pulse detection
  - `display`: Terminal UI with split-screen visualization
  - `api_server`: HTTP JSON endpoint on port 5002
  - `config`: Configuration management with YAML
- CLI per library:
  - `python -m mcp2221_sensor --test-connection`
  - `python -m display --demo`
  - `python -m api_server --port 5002`
- Library docs: llms.txt format planned? Yes

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? Yes
- Git commits show tests before implementation? Will be enforced
- Order: Contract→Integration→E2E→Unit strictly followed? Yes
- Real dependencies used? Yes (actual MCP2221A device for integration tests)
- Integration tests for: sensor detection, API contracts, configuration loading
- FORBIDDEN: Implementation before test, skipping RED phase

**Observability**:
- Structured logging included? Yes (structlog)
- Frontend logs → backend? N/A (single application)
- Error context sufficient? Yes (device states, timestamps, error types)

**Versioning**:
- Version number assigned? 0.1.0
- BUILD increments on every change? Yes
- Breaking changes handled? N/A (first version)

## Project Structure

### Documentation (this feature)
```
specs/001-mcp2221a-filament-sensor/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
│   ├── sensor_reading.py
│   ├── configuration.py
│   └── metrics.py
├── services/
│   ├── mcp2221_manager.py
│   ├── sensor_monitor.py
│   └── data_aggregator.py
├── cli/
│   ├── main.py
│   └── commands.py
└── lib/
    ├── mcp2221_sensor/
    ├── display/
    ├── api_server/
    └── config/

tests/
├── contract/
│   └── test_api_contracts.py
├── integration/
│   ├── test_sensor_detection.py
│   └── test_end_to_end.py
└── unit/
    ├── test_pulse_detection.py
    └── test_calibration.py
```

**Structure Decision**: Option 1 (Single project) - standalone monitoring application

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - ✅ MCP2221A Python library selection → EasyMCP2221 chosen
   - ✅ GPIO configuration for sensors → GP0-GP3 with pull-up
   - ✅ Terminal UI framework → Textual for split-screen
   - ✅ HTTP server framework → FastAPI on port 5002
   - ✅ Threading vs async architecture → Hybrid approach

2. **Generate and dispatch research agents**:
   ```
   ✅ Research MCP2221A USB-GPIO capabilities
   ✅ Research BIGTREETECH sensor specifications
   ✅ Research Python Windows development patterns
   ✅ Research real-time monitoring architectures
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: Technology choices documented
   - Rationale: Performance and compatibility focused
   - Alternatives considered: Multiple libraries evaluated

**Output**: research.md with all NEEDS CLARIFICATION resolved ✅

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - SensorReading: timestamp, sensor_id, presence, movement, pulse_count
   - Configuration: pins, calibration, polling_interval
   - Metrics: total_pulses, distance_meters, session_start
   - AlertEvent: timestamp, sensor_id, event_type

2. **Generate API contracts** from functional requirements:
   - GET /status → sensor states and metrics
   - GET /config → current configuration
   - POST /config → update configuration
   - WebSocket /stream → real-time updates

3. **Generate contract tests** from contracts:
   - test_status_endpoint_schema.py
   - test_config_endpoint_validation.py
   - test_websocket_messages.py

4. **Extract test scenarios** from user stories:
   - Dual sensor presence detection
   - Movement pulse counting
   - Filament runout alert generation
   - Configuration persistence

5. **Update agent file incrementally**:
   - CLAUDE.md with project context
   - Technology stack details
   - Recent changes tracking

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, CLAUDE.md

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P]
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation
- Dependency order: Models → Services → UI → API
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 30-35 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
**Phase 4**: Implementation (execute tasks.md following constitutional principles)
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*No violations - design follows constitutional principles*

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*