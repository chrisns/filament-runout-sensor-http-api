# Feature Specification: MCP2221A Dual Filament Sensor Monitor

**Feature Branch**: `001-mcp2221a-filament-sensor`
**Created**: 2025-09-15
**Status**: Draft
**Input**: User description: "you are running in WSL2 on a pc currently connected via USB to a MCP2221A - to that there is currently two BIGTREETECH Smart Filament Sensor Filament V2.0 Break Detection Module sensors. the both sensors should currently show as having filament one of the filaments is moving, the other is not you should make some assumptions over the sensor configs in terms of what pins they are on so that these can be paramatised somewhere easily configurable and changable in the future The 3d printer is currently 3d printing on one filament so you should make the necessary assumptions to run this I want this to run natively in windows as python, so write the application in that, dependencies are fine, but keep them to a minimum and use a package manager"

## Execution Flow (main)
```
1. Parse user description from Input
   → If empty: ERROR "No feature description provided"
2. Extract key concepts from description
   → Identify: actors, actions, data, constraints
3. For each unclear aspect:
   → Mark with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   → If no clear user flow: ERROR "Cannot determine user scenarios"
5. Generate Functional Requirements
   → Each requirement must be testable
   → Mark ambiguous requirements
6. Identify Key Entities (if data involved)
7. Run Review Checklist
   → If any [NEEDS CLARIFICATION]: WARN "Spec has uncertainties"
   → If implementation details found: ERROR "Remove tech details"
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

### Section Requirements
- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation
When creating this spec from a user prompt:
1. **Mark all ambiguities**: Use [NEEDS CLARIFICATION: specific question] for any assumption you'd need to make
2. **Don't guess**: If the prompt doesn't specify something (e.g., "login system" without auth method), mark it
3. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
4. **Common underspecified areas**:
   - User types and permissions
   - Data retention/deletion policies
   - Performance targets and scale
   - Error handling behaviors
   - Integration requirements
   - Security/compliance needs

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a 3D printer operator, I need to monitor two filament sensors connected through a USB MCP2221A adapter to ensure continuous filament supply during printing operations. The system should detect filament presence/absence, monitor movement for the active filament, and provide real-time status updates for both sensors simultaneously.

### Acceptance Scenarios
1. **Given** both filament sensors have filament loaded and the system is running, **When** the operator checks the status, **Then** the system displays both sensors as having filament present
2. **Given** one filament is actively being used for printing, **When** monitoring sensor activity, **Then** the system shows movement detection for the active sensor and no movement for the idle sensor
3. **Given** a filament runs out during printing, **When** the sensor detects the break/absence, **Then** the system immediately alerts the operator with clear identification of which sensor triggered
4. **Given** the system is configured with default pin assignments, **When** an operator needs different pin configurations, **Then** they can modify the configuration without code changes
5. **Given** the terminal display is running, **When** viewing the output, **Then** each extruder status is clearly separated and shows filament presence, movement, and usage in meters
6. **Given** the HTTP server is running on port 5002, **When** accessing the JSON endpoint, **Then** the response includes runout status and filament usage for both sensors
7. **Given** filament is feeding through sensor 1, **When** 100 pulses are detected with default calibration, **Then** the system shows 0.288 meters of filament used

### Edge Cases
- What happens when the MCP2221A USB connection is lost during operation?
- How does system handle sensor signal noise or intermittent false readings?
- What occurs if both sensors trigger simultaneously?
- How does the system behave when started without the MCP2221A connected?
- What happens if configured pins conflict with each other?

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: System MUST detect and connect to MCP2221A USB adapter automatically when available
- **FR-002**: System MUST monitor two independent filament sensors simultaneously
- **FR-003**: System MUST detect filament presence/absence state for each sensor
- **FR-004**: System MUST detect filament movement (motion) for actively feeding sensors
- **FR-005**: System MUST provide real-time status display showing both sensors' states
- **FR-006**: System MUST alert operator immediately when filament break/runout is detected
- **FR-007**: System MUST identify which specific sensor (1 or 2) triggered any alert
- **FR-008**: System MUST allow configuration of GPIO pin assignments without code modification
- **FR-009**: System MUST handle USB disconnection gracefully and attempt reconnection
- **FR-010**: System MUST differentiate between moving and stationary filament
- **FR-011**: System MUST log all sensor state changes with timestamps
- **FR-012**: System MUST provide visual distinction between active (moving) and idle sensors
- **FR-013**: System MUST validate pin configuration on startup to prevent conflicts
- **FR-014**: System MUST support configurable polling interval for sensor reads (default: 100ms)
- **FR-015**: System MUST retain sensor event history for current session only
- **FR-016**: System MUST log filament runout events with timestamp and sensor identification
- **FR-017**: System MUST display real-time status in terminal with visual separation for each extruder
- **FR-018**: System MUST show current filament status, movement state, and usage statistics for each sensor
- **FR-019**: System MUST provide HTTP server on port 5002 serving JSON API
- **FR-020**: System MUST expose sensor status and filament usage data via JSON endpoint
- **FR-021**: System MUST track filament consumption based on movement pulses
- **FR-022**: System MUST support configurable pulse-to-distance calibration (default: 2.88mm per pulse)
- **FR-023**: System MUST calculate and display total filament used per sensor in meters
- **FR-024**: System MUST update terminal display in real-time as sensor states change
- **FR-025**: JSON API MUST return current runout status and cumulative filament usage for both sensors

### Key Entities *(include if feature involves data)*
- **Filament Sensor**: Represents a BIGTREETECH Smart Filament Sensor V2.0, tracking presence state, movement state, assigned GPIO pin, sensor identifier (1 or 2), and cumulative pulse count
- **Sensor Reading**: Captures timestamp, sensor ID, presence state, movement detected flag, raw signal value, and pulse increment
- **Alert Event**: Records alert timestamp, triggering sensor ID, alert type (runout/break), and acknowledgment status
- **Configuration Settings**: Stores GPIO pin assignments for each sensor, polling intervals, alert thresholds, and pulse-to-distance calibration factor
- **Usage Metrics**: Tracks total pulses counted, calculated distance in meters, and session start time for each sensor
- **API Response**: Structures JSON output containing sensor states, runout status, and filament usage statistics

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---