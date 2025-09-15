"""SensorConfiguration data model for hardware and calibration settings."""

from typing import Dict, Any
from pydantic import BaseModel, Field, field_validator, computed_field


class GPIOMapping(BaseModel):
    """GPIO pin mapping for a single sensor."""

    movement_pin: int = Field(ge=0, le=3, description="GPIO pin for movement detection")
    runout_pin: int = Field(ge=0, le=3, description="GPIO pin for runout detection")

    @field_validator('movement_pin', 'runout_pin')
    @classmethod
    def validate_gpio_pin(cls, v: int) -> int:
        """Validate GPIO pin is 0-3 (MCP2221A has 4 GPIO pins)."""
        if v not in range(4):
            raise ValueError("GPIO pin must be 0-3")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate pins are not the same."""
        if self.movement_pin == self.runout_pin:
            raise ValueError("Movement and runout pins cannot be the same")


class CalibrationSettings(BaseModel):
    """Calibration settings for distance calculations."""

    mm_per_pulse: float = Field(
        default=2.88,
        gt=0.0,
        le=100.0,
        description="Millimeters of filament per pulse"
    )
    debounce_ms: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Debounce time in milliseconds"
    )
    runout_threshold_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Time without movement to trigger runout (ms)"
    )

    @field_validator('mm_per_pulse')
    @classmethod
    def validate_mm_per_pulse(cls, v: float) -> float:
        """Validate and round mm_per_pulse."""
        return round(v, 4)


class PollingSettings(BaseModel):
    """Polling and timing configuration."""

    polling_interval_ms: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Sensor polling interval in milliseconds"
    )
    ui_update_interval_ms: int = Field(
        default=100,
        ge=50,
        le=1000,
        description="UI update interval in milliseconds"
    )
    api_response_timeout_ms: int = Field(
        default=5000,
        ge=1000,
        le=30000,
        description="API response timeout in milliseconds"
    )

    @computed_field
    @property
    def polling_frequency_hz(self) -> float:
        """Calculate polling frequency in Hz."""
        return 1000.0 / self.polling_interval_ms


class SensorConfiguration(BaseModel):
    """Complete sensor system configuration."""

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "sensor1_gpio": {"movement_pin": 0, "runout_pin": 1},
                "sensor2_gpio": {"movement_pin": 2, "runout_pin": 3},
                "calibration": {"mm_per_pulse": 2.88, "debounce_ms": 10},
                "polling": {"polling_interval_ms": 100}
            }
        }
    }

    # GPIO configuration
    sensor1_gpio: GPIOMapping = Field(
        default=GPIOMapping(movement_pin=0, runout_pin=1),
        description="GPIO mapping for sensor 1"
    )
    sensor2_gpio: GPIOMapping = Field(
        default=GPIOMapping(movement_pin=2, runout_pin=3),
        description="GPIO mapping for sensor 2"
    )

    # Calibration settings
    calibration: CalibrationSettings = Field(
        default_factory=CalibrationSettings,
        description="Calibration parameters"
    )

    # Polling configuration
    polling: PollingSettings = Field(
        default_factory=PollingSettings,
        description="Polling and timing settings"
    )

    # System settings
    enable_debug_logging: bool = Field(
        default=False,
        description="Enable debug level logging"
    )
    api_port: int = Field(
        default=5002,
        ge=1024,
        le=65535,
        description="HTTP API server port"
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate GPIO pin assignments don't conflict."""
        used_pins = {
            self.sensor1_gpio.movement_pin,
            self.sensor1_gpio.runout_pin,
            self.sensor2_gpio.movement_pin,
            self.sensor2_gpio.runout_pin
        }

        if len(used_pins) != 4:
            raise ValueError("All GPIO pins must be unique")

    @computed_field
    @property
    def gpio_pin_map(self) -> Dict[int, str]:
        """Map GPIO pins to their functions."""
        return {
            self.sensor1_gpio.movement_pin: "sensor1_movement",
            self.sensor1_gpio.runout_pin: "sensor1_runout",
            self.sensor2_gpio.movement_pin: "sensor2_movement",
            self.sensor2_gpio.runout_pin: "sensor2_runout"
        }

    def get_sensor_pins(self, sensor_id: int) -> GPIOMapping:
        """Get GPIO mapping for specific sensor."""
        if sensor_id == 1:
            return self.sensor1_gpio
        elif sensor_id == 2:
            return self.sensor2_gpio
        else:
            raise ValueError("sensor_id must be 1 or 2")

    def export_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary for JSON serialization."""
        return self.model_dump(mode='json')