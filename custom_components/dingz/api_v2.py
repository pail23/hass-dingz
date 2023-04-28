import dataclasses
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Union
from .api import (
    FromJSON,
    Info,
    Device,
    State,
    BlindConfig,
    PIRConfig,
    TempComp,
    Dimmer,
    Blind,
    LED,
    WiFi,
    Config,
)

import aiohttp
from voluptuous.validators import Boolean

logger = logging.getLogger(__name__)


@dataclasses.dataclass()
class ThermostatV2(FromJSON):
    active: bool
    """If the thermostat functionality is enabled."""
    # API 2 out: int
    """The output index assigned to thermostat."""
    # API 2 on: bool
    """If the output controlled by thermostat is turn on."""
    enabled: bool
    """It the thermostat is enabled e.g. control output depending of temperature."""
    target_temp: float
    """The target cooling heating temperature."""
    mode: str
    """Mode of thermostat operating."""
    temp: float
    """Current room temperature."""
    min_target_temp: int
    """Minimum target temperature."""
    max_target_temp: int
    """Maximum target temperature."""


@dataclasses.dataclass()
class DimmerConfigV2(FromJSON):
    @dataclasses.dataclass()
    class Feedback(FromJSON):
        color: str
        brightness: int

    @dataclasses.dataclass()
    class Light(FromJSON):
        @dataclasses.dataclass()
        class Dimmer(FromJSON):
            type: str
            use_last_value: bool

        dimmable: bool
        dimmer: Dimmer

        @classmethod
        def _from_json(cls, data):
            data["dimmer"] = cls.Dimmer.from_json(data["dimmer"])
            return super()._from_json(data)

    name: str
    """Name of dimmer (max 32 chars)."""
    feedback: Feedback
    """Signalize by enable LED with specified color when the dimmer is turn on.

    In case of multi dimmers set with feedback color enabled the color will be set to value get from first turned on dimmer.
    """

    light: Optional[Light] = None

    @property
    def dimmable(self) -> bool:
        return self.light is not None and self.light.dimmable

    @property
    def output(self) -> str:
        return self.light is not None and self.light.dimmer.type

    @property
    def available(self) -> bool:
        return bool(self.name)  # API 2: and self.output != DIMMER_NOT_CONNECTED

    @classmethod
    def _from_json(cls, data):
        data["light"] = cls.Light.from_json(data["light"])
        return super()._from_json(data)


@dataclasses.dataclass()
class SystemConfigV2(FromJSON):
    @dataclasses.dataclass()
    class Time(FromJSON):
        hour: int
        minute: int

    @dataclasses.dataclass()
    class DynLight(FromJSON):
        @dataclasses.dataclass()
        class SunOffset(FromJSON):
            day: int
            twilight: int
            night: int

        enable: bool
        phases: int
        source: str
        sun_offset: SunOffset

        @classmethod
        def _from_json(cls, data):
            data["sun_offset"] = cls.SunOffset.from_json(data["sun_offset"])
            return super()._from_json(data)

    allow_reset: bool
    """If the factory reset should be possible with the buttons."""
    allow_wps: bool
    """If it should be possible to enable WPS from the buttons."""
    allow_reboot: bool
    """If the restart should be possible from the buttons."""
    allow_remote_reboot: bool
    protected_status: bool
    id: bool
    lat: str
    long: str
    wifi_ps: bool
    tzid: int

    origin: bool
    """Whether the Origin HTTP header should be checked.

    In case of a mismatch, the query rejected.
    """
    upgrade_blink: bool
    """Should the LED flash pink while updating the firmware."""
    reboot_blink: bool
    """Should the LED flash blue after reboot."""
    dingz_name: bool
    """Device name (max 32 chars)"""
    room_name: str
    """Name of the room in which the device is located (max 32 chars)"""
    temp_offset: int
    """Offset of the temperature measured by the device (-10..10)

    Form of compensation.
    """
    time: str
    """This field is read-only and returns the date and time from the device.

    ("YYYY-MM-DD hh:mm:ss")
    """
    system_status: str
    """Specifies the puck status.

    Is there communication with it, are the outputs not overloaded, are the temperature not exceeded.

    Values:
    - "OK"
    - "Puck not responding"
    - "Puck overload"
    - "Puck FETs over temperature"
    """
    fet_offset: int
    """Read only. Temperature offset measured at the output transistors (-100..100)."""
    cpu_offset: int
    """Read only. Temperature offset measured on the puck CPU (-100..100)."""
    token: Optional[str] = None
    """Sets a Token for HTTP requests (max 256 chars).

    If the correct token is not provided, the query will be rejected.
    """
    mdns_search_period: Optional[int] = None
    groups: Optional[List[bool]] = None
    temp_comp: Optional[TempComp] = None

    dyn_light: Optional[DynLight] = None
    sunrise: Optional[Time] = None
    sunset: Optional[Time] = None

    @classmethod
    def _from_json(cls, data):
        data["sunrise"] = cls.Time.from_json(data["sunrise"])
        data["sunset"] = cls.Time.from_json(data["sunset"])
        data["dyn_light"] = cls.DynLight.from_json(data["dyn_light"])
        try:
            raw_temp_comp = data.pop("temp_comp")
        except KeyError:
            pass
        else:
            data["temp_comp"] = TempComp.from_json(raw_temp_comp)

        return super()._from_json(data)


@dataclasses.dataclass()
class SensorsV2(FromJSON):
    @dataclasses.dataclass()
    class PIR(FromJSON):
        enabled: bool
        motion: bool
        mode: str
        light_off_timer: int
        suspend_timer: int

        @classmethod
        def from_json(cls, data: dict):
            if data is None:
                return None
            else:
                try:
                    return cls._from_json(data.copy())
                except Exception as e:
                    if not getattr(e, "_handled", False):
                        logger.error(
                            f"failed to create `{cls.__qualname__}` from JSON: {data!r}"
                        )
                        e._handled = True

                    raise e from None

    brightness: Optional[int]
    """The brightness read by light sensor including compensation of light depending on cover color.

    If there is  error or no light sensor is present the field is set to `None`.
    """
    light_state: Optional[str]
    """The field contains the range in which the illuminance is located.

    It can have values: day, twilight or night. The assignment to the interval depends on the settings in the WebUI/Motion Detector/Thresholds.
    In case of error or light sensor not present the field contain null value.
    """
    light_state_lpf: Optional[str]
    """The field contains the range in which the illuminance is located.

    It can have values: day, twilight or night. The assignment to the interval depends on the settings in the WebUI/Motion Detector/Thresholds.
    In case of error or light sensor not present the field contain null value.
    """
    cpu_temperature: float
    """The temperature on front CPU."""
    puck_temperature: Optional[float]
    """The temperature on back CPU.

    If there is any error then this field contain null value.
    """
    fet_temperature: Optional[float]
    """The internal puck/base FET temperature.

    If there is any error then this field contain null value.
    """
    @property
    def person_present(self) -> Optional[bool]:
        """The current status of motion."""
        if self.pirs[0] is not None:
            return self.pirs[0].motion
        elif self.pirs[1] is not None:
            return self.pirs[1].motion
        else:
            return None

    pirs: List[Optional[PIR]]

    input_state: Optional[bool]
    """If the output 1 is not configured as input then the field contain null value otherwise bool value represent input state (the voltage present on input).

    The input state can be negated in input settings (WebUI/Input/invert).
    """
    power_outputs: Optional[List[float]]
    """This field contain array of objects.

    Each object contain the value field which show the current power provided to device connected to output.
    This field can have the null value in case of any failure.
    """

    room_temperature: Optional[float] = None
    """The compensated temperature in room.

    If there is any error the field is not present.
    """
    uncompensated_temperature: Optional[float] = None
    """The uncompensated temperature in room (measured by temperature sensor).

    If there is any error the field is not present.
    """
    temp_offset: Optional[float] = None
    light_off_timer: Optional[int] = None
    """If the PIR timer is enabled on any output then this field is present and show how much time left to turn off the output."""
    suspend_timer: Optional[int] = None
    """If the PIR timer is enabled on any output then this field is present and show how much time left to turn on the output by PIR sensor will be possible."""

    @classmethod
    def _from_json(cls, data):
        data["pirs"] = cls.PIR.list_from_json(data["pirs"])
        power_outputs = data["power_outputs"]
        if power_outputs:
            try:
                for i, out in enumerate(power_outputs):
                    power_outputs[i] = out["value"]
            except Exception:
                logger.error("failed to handle power outputs")
                raise

        return super()._from_json(data)


@dataclasses.dataclass()
class StateV2(FromJSON):
    dimmers: List[Dimmer]
    blinds: List[Blind]
    led: LED
    sensors: SensorsV2
    thermostat: ThermostatV2
    wifi: WiFi
    config: Config
    # iso timestamps in the form of `yyyy-mm-dd HH:MM:SS`
    time: Optional[str] = None

    @classmethod
    def _from_json(cls, data):
        data["dimmers"] = Dimmer.list_from_json(data["dimmers"])
        data["blinds"] = Blind.list_from_json(data["blinds"])
        data["led"] = LED.from_json(data["led"])
        data["sensors"] = SensorsV2.from_json(data["sensors"])
        data["thermostat"] = ThermostatV2.from_json(data["thermostat"])
        data["wifi"] = WiFi.from_json(data["wifi"])
        data["config"] = Config.from_json(data["config"])
        return super()._from_json(data)


@dataclasses.dataclass()
class DingzSessionV2:
    session: aiohttp.ClientSession
    host: str

    async def _get(self, path: str):
        async with self.session.get(f"{self.host}/api/v1{path}") as resp:
            return await resp.json()

    def __post_request(self, path: str, data: Optional[dict]):
        headers = {}
        if data:
            # doing it by hand to avoid percent encoding
            body = "&".join(f"{key}={value}" for key, value in data.items())
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = None

        logger.debug("POST %s | %s", path, body)
        return self.session.post(
            f"{self.host}/api/v1{path}",
            data=body,
            headers=headers,
        )

    async def _post_json(self, path: str, **data):
        async with self.__post_request(path, data) as resp:
            logger.debug("response: %s", resp)
            return await resp.json()

    async def _post_plain(self, path: str, **data):
        async with self.__post_request(path, data) as resp:
            logger.debug("response: %s", resp)
            resp.raise_for_status()

    async def info(self) -> Info:
        raw = await self._get("/info")
        return Info.from_json(raw)

    async def device(self) -> Device:
        raw = await self._get("/device")
        if len(raw) > 1:
            logger.warning(f"received more than one device: {raw}")
        try:
            device_raw = next(iter(raw.values()))
        except StopIteration:
            logger.error("empty device response")
            raise

        return Device.from_json(device_raw)

    async def state(self) -> State:
        raw = await self._get("/state")
        return StateV2.from_json(raw)

    async def system_config(self) -> SystemConfigV2:
        raw = await self._get("/system_config")
        return SystemConfigV2.from_json(raw)

    async def dimmer_config(self) -> List[DimmerConfigV2]:
        raw = await self._get("/dimmer_config")
        return DimmerConfigV2.list_from_json(raw["dimmers"])

    async def blind_config(self) -> List[BlindConfig]:
        raw = await self._get("/blind_config")
        return BlindConfig.list_from_json(raw["blinds"])

    async def pir_config(self) -> PIRConfig:
        raw = await self._get("/pir_config")
        return PIRConfig.from_json(raw)

    async def set_led(
        self, *, state: bool = None, color: Tuple[float, float, float] = None
    ) -> None:
        """
        Args:
            state: Requested state. `None` toggles.
            color: (<0...359>, <0..100>, <0..100>)
        """
        kwargs = {}
        if color:
            h, s, v = map(round, color)
            kwargs["color"] = f"{h % 360};{s};{v}"
            kwargs["mode"] = "hsv"

        action = "toggle" if state is None else "on" if state else "off"

        await self._post_json("/led/set", action=action, **kwargs)

    async def set_dimmer(self, index: int, state: bool, *, value: float = None) -> None:
        kwargs = {}
        if value is not None:
            kwargs["value"] = round(value)
        action = "on" if state else "off"
        await self._post_plain(f"/dimmer/{index}/{action}", **kwargs)

    async def set_blind_position(self, index: int, position: float) -> None:
        kwargs = {}
        kwargs["blind"] = round(position)
        await self._post_plain(f"/shade/{index}", **kwargs)

    async def blind_down(self, index: int) -> None:
        kwargs = {}
        await self._post_plain(f"/shade/{index}/down", **kwargs)

    async def blind_up(self, index: int) -> None:
        kwargs = {}
        await self._post_plain(f"/shade/{index}/up", **kwargs)

    async def blind_stop(self, index: int) -> None:
        kwargs = {}
        await self._post_plain(f"/shade/{index}/stop", **kwargs)
