"""
MQTT Discovery Helper for Home Assistant
Provides unique_id support for sensors
"""

import json
import logging
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

TOPIC_PREFIX = "dhlotto"


class MQTTDiscovery:
    """MQTT Discovery helper class"""
    
    def __init__(self, mqtt_url: str, username: Optional[str] = None, password: Optional[str] = None, client_id_suffix: str = ""):
        """Initialize MQTT Discovery
        
        Args:
            mqtt_url: MQTT URL (e.g., "mqtt://192.168.1.118:1883" or "homeassistant.local:1883")
            username: MQTT username (optional)
            password: MQTT password (optional)
            client_id_suffix: Suffix for MQTT client ID to avoid conflicts (e.g., "_beta")
        """
        # Parse MQTT URL
        self.broker, self.port = self._parse_mqtt_url(mqtt_url)
        self.username_mqtt = username
        self.password_mqtt = password
        self.client_id_suffix = client_id_suffix
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.connecting = False
    
    @staticmethod
    def _parse_mqtt_url(mqtt_url: str) -> tuple:
        """Parse MQTT URL
        
        Args:
            mqtt_url: MQTT URL (e.g., "mqtt://192.168.1.118:1883" or "homeassistant.local:1883")
            
        Returns:
            tuple: (broker, port)
        """
        # Add mqtt:// prefix if not present
        if not mqtt_url.startswith("mqtt://"):
            mqtt_url = f"mqtt://{mqtt_url}"
        
        parsed = urlparse(mqtt_url)
        broker = parsed.hostname or "homeassistant.local"
        port = parsed.port or 1883
        
        return broker, port
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        if self.connecting or self.connected:
            return self.connected
        
        try:
            self.connecting = True
            # Create unique client ID with suffix to avoid conflicts
            client_id = f"dhlottery_addon{self.client_id_suffix}"
            self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            
            if self.username_mqtt and self.password_mqtt:
                self.client.username_pw_set(self.username_mqtt, self.password_mqtt)
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            _LOGGER.info(f"Connecting to MQTT broker: {self.broker}:{self.port} (client_id: {client_id})")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            # Wait for connection (max 5 seconds)
            timeout = 5
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                _LOGGER.error("MQTT connection timeout")
                self.connecting = False
                return False
            
            _LOGGER.info("Successfully connected to MQTT broker")
            self.connecting = False
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to connect to MQTT broker: {e}")
            self.connecting = False
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to MQTT broker")
        else:
            _LOGGER.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        _LOGGER.warning(f"Disconnected from MQTT broker: {rc}")
    
    def publish_sensor_discovery(
        self,
        sensor_id: str,
        name: str,
        state_topic: str,
        username: str,
        device_name: Optional[str] = None,
        device_identifier: Optional[str] = None,
        unit_of_measurement: Optional[str] = None,
        device_class: Optional[str] = None,
        icon: Optional[str] = None,
        value_template: Optional[str] = None,
        json_attributes_topic: Optional[str] = None,
    ) -> bool:
        """
        Publish sensor discovery configuration
        
        Args:
            sensor_id: Sensor ID (e.g., 'balance', 'hot_numbers')
            name: Friendly name
            state_topic: MQTT topic for state
            username: DH Lottery username (for unique_id)
            device_name: Device name (optional, uses default if not provided)
            device_identifier: Device identifier (optional, uses default if not provided)
            unit_of_measurement: Unit (e.g., 'KRW', 'times')
            device_class: Device class (e.g., 'timestamp', 'date')
            icon: Icon (e.g., 'mdi:wallet')
            value_template: Jinja2 template for value
            json_attributes_topic: Topic for attributes
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Use default device if not specified
        if not device_name:
            device_name = f"ë™í–‰ë³µê¶Œ ì• ë“œì˜¨ ({username})"
        if not device_identifier:
            device_identifier = f"{TOPIC_PREFIX}_addon_{username}"
        
        # Discovery topic: homeassistant/sensor/dhlotto_USERNAME_SENSOR_ID/config
        discovery_topic = f"homeassistant/sensor/{TOPIC_PREFIX}_{username}_{sensor_id}/config"
        
        # Unique ID: dhlotto_USERNAME_SENSOR_ID
        unique_id = f"{TOPIC_PREFIX}_{username}_{sensor_id}"
        
        # Entity ID: sensor.dhlotto_USERNAME_SENSOR_ID
        object_id = f"{TOPIC_PREFIX}_{username}_{sensor_id}"
        
        config = {
            "name": name,
            "unique_id": unique_id,
            "object_id": object_id,
            "state_topic": state_topic,
            "device": {
                "identifiers": [device_identifier],
                "name": device_name,
                "manufacturer": "DH Lottery",
                "model": "Add-on",
                "sw_version": "1.0.0",
            },
        }
        
        # Optional fields
        if unit_of_measurement:
            config["unit_of_measurement"] = unit_of_measurement
        if device_class:
            config["device_class"] = device_class
        if icon:
            config["icon"] = icon
        if value_template:
            config["value_template"] = value_template
        if json_attributes_topic:
            config["json_attributes_topic"] = json_attributes_topic
        
        try:
            payload = json.dumps(config, ensure_ascii=False)
            result = self.client.publish(discovery_topic, payload, qos=1, retain=True)
            result.wait_for_publish()
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to publish discovery for {sensor_id}: {e}")
            return False
    
    def publish_sensor_state(self, sensor_id: str, username: str, state: Any, 
                            attributes: Optional[Dict[str, Any]] = None) -> bool:
        """
        Publish sensor state
        
        Args:
            sensor_id: Sensor ID
            username: DH Lottery username
            state: Sensor state value
            attributes: Optional attributes dictionary
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # State topic
        state_topic = f"homeassistant/sensor/{TOPIC_PREFIX}_{username}_{sensor_id}/state"
        
        try:
            # Publish state
            result = self.client.publish(state_topic, str(state), qos=1, retain=True)
            result.wait_for_publish()
            
            # Publish attributes if provided
            if attributes:
                attr_topic = f"homeassistant/sensor/{TOPIC_PREFIX}_{username}_{sensor_id}/attributes"
                attr_payload = json.dumps(attributes, ensure_ascii=False)
                result = self.client.publish(attr_topic, attr_payload, qos=1, retain=True)
                result.wait_for_publish()
            
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to publish state for {sensor_id}: {e}")
            return False
    
    def remove_sensor(self, sensor_id: str, username: str) -> bool:
        """
        Remove sensor from Home Assistant (publish empty config)
        
        Args:
            sensor_id: Sensor ID
            username: DH Lottery username
        """
        if not self.connected:
            return False
        
        discovery_topic = f"homeassistant/sensor/{TOPIC_PREFIX}_{username}_{sensor_id}/config"
        
        try:
            result = self.client.publish(discovery_topic, "", qos=1, retain=True)
            result.wait_for_publish()
            _LOGGER.info(f"Removed sensor: {sensor_id}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to remove sensor {sensor_id}: {e}")
            return False
    
    def publish_input_text_discovery(
        self,
        input_id: str,
        name: str,
        state_topic: str,
        command_topic: str,
        username: str,
        device_name: str,
        device_identifier: str,
        icon: Optional[str] = None,
        pattern: Optional[str] = None,
        mode: str = "text",
    ) -> bool:
        """
        Publish input_text discovery configuration
        
        Args:
            input_id: Input text ID (e.g., 'manual_numbers')
            name: Friendly name
            state_topic: MQTT topic for state
            command_topic: MQTT topic for commands
            username: DH Lottery username
            device_name: Device name
            device_identifier: Device identifier
            icon: Icon (e.g., 'mdi:numeric')
            pattern: Regex pattern for validation
            mode: Input mode ('text' or 'password')
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Discovery topic: homeassistant/text/dhlotto_USERNAME_INPUT_ID/config
        discovery_topic = f"homeassistant/text/{TOPIC_PREFIX}_{username}_{input_id}/config"
        
        # Unique ID: dhlotto_USERNAME_INPUT_ID
        unique_id = f"{TOPIC_PREFIX}_{username}_{input_id}"
        
        # Entity ID: text.dhlotto_USERNAME_INPUT_ID
        object_id = f"{TOPIC_PREFIX}_{username}_{input_id}"
        
        config = {
            "name": name,
            "unique_id": unique_id,
            "object_id": object_id,
            "state_topic": state_topic,
            "command_topic": command_topic,
            "mode": mode,
            "device": {
                "identifiers": [device_identifier],
                "name": device_name,
                "manufacturer": "DH Lottery",
                "model": "Add-on",
                "sw_version": "1.0.0",
            },
        }
        
        # Optional fields
        if icon:
            config["icon"] = icon
        if pattern:
            config["pattern"] = pattern
        
        try:
            payload = json.dumps(config, ensure_ascii=False)
            _LOGGER.debug(f"Publishing input_text discovery: {discovery_topic}")
            _LOGGER.debug(f"Config: {payload}")
            result = self.client.publish(discovery_topic, payload, qos=1, retain=True)
            result.wait_for_publish()
            _LOGGER.info(f"Published input_text discovery: text.{object_id}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to publish input_text discovery for {input_id}: {e}")
            return False
    
    def publish_button_discovery(
        self,
        button_id: str,
        name: str,
        command_topic: str,
        username: str,
        device_name: str,
        device_identifier: str,
        icon: Optional[str] = None,
        device_class: Optional[str] = None,
    ) -> bool:
        """
        Publish button discovery configuration
        
        Args:
            button_id: Button ID (e.g., 'buy_auto_1', 'buy_auto_5')
            name: Friendly name
            command_topic: MQTT topic for commands
            username: DH Lottery username
            device_name: Device name (e.g., "DH Lottery Lotto 645 (ng410808)")
            device_identifier: Device identifier (e.g., "dhlotto_ng410808_lotto645")
            icon: Icon (e.g., 'mdi:ticket-confirmation')
            device_class: Device class (e.g., 'restart')
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Discovery topic: homeassistant/button/dhlotto_USERNAME_BUTTON_ID/config
        discovery_topic = f"homeassistant/button/{TOPIC_PREFIX}_{username}_{button_id}/config"
        
        # Unique ID: dhlotto_USERNAME_BUTTON_ID
        unique_id = f"{TOPIC_PREFIX}_{username}_{button_id}"
        
        # Entity ID: button.dhlotto_USERNAME_BUTTON_ID
        object_id = f"{TOPIC_PREFIX}_{username}_{button_id}"
        
        config = {
            "name": name,
            "unique_id": unique_id,
            "object_id": object_id,
            "command_topic": command_topic,
            "device": {
                "identifiers": [device_identifier],
                "name": device_name,
                "manufacturer": "DH Lottery",
                "model": "Add-on",
                "sw_version": "1.0.0",
            },
        }
        
        # Optional fields
        if icon:
            config["icon"] = icon
        if device_class:
            config["device_class"] = device_class
        
        try:
            payload = json.dumps(config, ensure_ascii=False)
            _LOGGER.debug(f"Publishing button discovery: {discovery_topic}")
            _LOGGER.debug(f"Config: {payload}")
            result = self.client.publish(discovery_topic, payload, qos=1, retain=True)
            result.wait_for_publish()
            _LOGGER.info(f"Published button discovery: button.{object_id}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to publish button discovery for {button_id}: {e}")
            return False
    
    def subscribe_to_commands(self, username: str, callback) -> bool:
        """
        Subscribe to button command topics and input text set topics
        
        Args:
            username: DH Lottery username
            callback: Callback function to handle messages
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Subscribe to Lotto 645 button commands
        button_ids = ["buy_auto_1", "buy_auto_5", "buy_manual"]
        
        # Subscribe to input text
        input_ids = ["manual_numbers"]
        
        try:
            self.client.on_message = callback
            
            # Subscribe to buttons
            for button_id in button_ids:
                command_topic = f"homeassistant/button/{TOPIC_PREFIX}_{username}_{button_id}/command"
                result = self.client.subscribe(command_topic)
                _LOGGER.info(f"Subscribed to button: {command_topic}")
            
            # Subscribe to input text
            for input_id in input_ids:
                set_topic = f"homeassistant/text/{TOPIC_PREFIX}_{username}_{input_id}/set"
                result = self.client.subscribe(set_topic)
                _LOGGER.info(f"Subscribed to input text: {set_topic}")
            
            _LOGGER.info("Waiting for button press and input text change events...")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to subscribe to commands: {e}")
            return False


async def publish_sensor_mqtt(
    mqtt_client: MQTTDiscovery,
    entity_id: str,
    state: Any,
    username: str,
    attributes: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Helper function to publish sensor via MQTT Discovery
    
    Args:
        mqtt_client: MQTT Discovery client
        entity_id: Entity ID (e.g., 'lotto45_balance')
        state: Sensor state
        username: DH Lottery username
        attributes: Sensor attributes (includes friendly_name, icon, etc.)
    """
    if not mqtt_client or not mqtt_client.connected:
        return False
    
    # Extract metadata from attributes
    friendly_name = attributes.get("friendly_name", entity_id) if attributes else entity_id
    unit = attributes.get("unit_of_measurement")
    device_class = attributes.get("device_class")
    icon = attributes.get("icon")
    
    # Prepare state topic
    state_topic = f"homeassistant/sensor/{TOPIC_PREFIX}_{username}_{entity_id}/state"
    
    # Prepare attributes topic
    json_attributes_topic = None
    if attributes:
        json_attributes_topic = f"homeassistant/sensor/{TOPIC_PREFIX}_{username}_{entity_id}/attributes"
    
    # Only log important sensors
    is_important = "purchase" in entity_id or "latest" in entity_id
    if is_important:
        _LOGGER.info(f"Publishing MQTT sensor: {entity_id} = {state}")
    
    # Publish discovery config (only once, but retained)
    mqtt_client.publish_sensor_discovery(
        sensor_id=entity_id,
        name=friendly_name,
        state_topic=state_topic,
        username=username,
        unit_of_measurement=unit,
        device_class=device_class,
        icon=icon,
        json_attributes_topic=json_attributes_topic,
    )
    
    # Publish state
    result = mqtt_client.publish_sensor_state(
        sensor_id=entity_id,
        username=username,
        state=state,
        attributes=attributes
    )
    
    if is_important and result:
        _LOGGER.info(f"MQTT sensor published: {entity_id}")
    
    return result

