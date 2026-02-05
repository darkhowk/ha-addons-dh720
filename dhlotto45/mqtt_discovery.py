"""
MQTT Discovery Helper for Home Assistant
Provides unique_id support for sensors
"""

import json
import logging
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


class MQTTDiscovery:
    """MQTT Discovery helper class"""
    
    def __init__(self, broker: str = "homeassistant.local", port: int = 1883, 
                 username: Optional[str] = None, password: Optional[str] = None):
        """Initialize MQTT Discovery"""
        self.broker = broker
        self.port = port
        self.username_mqtt = username
        self.password_mqtt = password
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client(client_id="dhlottery_addon", protocol=mqtt.MQTTv5)
            
            if self.username_mqtt and self.password_mqtt:
                self.client.username_pw_set(self.username_mqtt, self.password_mqtt)
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to MQTT broker")
        else:
            _LOGGER.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        _LOGGER.warning(f"Disconnected from MQTT broker: {rc}")
    
    def publish_sensor_discovery(
        self,
        sensor_id: str,
        name: str,
        state_topic: str,
        username: str,
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
            unit_of_measurement: Unit (e.g., 'KRW', 'times')
            device_class: Device class (e.g., 'timestamp', 'date')
            icon: Icon (e.g., 'mdi:wallet')
            value_template: Jinja2 template for value
            json_attributes_topic: Topic for attributes
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Discovery topic: homeassistant/sensor/dhlottery_addon_USERNAME_SENSOR_ID/config
        discovery_topic = f"homeassistant/sensor/dhlottery_addon_{username}_{sensor_id}/config"
        
        # Unique ID: dhlottery_addon_USERNAME_SENSOR_ID
        unique_id = f"dhlottery_addon_{username}_{sensor_id}"
        
        # Entity ID: sensor.dhlottery_addon_USERNAME_SENSOR_ID
        object_id = f"dhlottery_addon_{username}_{sensor_id}"
        
        config = {
            "name": name,
            "unique_id": unique_id,
            "default_entity_id": f"sensor.{object_id}",
            "state_topic": state_topic,
            "device": {
                "identifiers": [f"dhlottery_addon_{username}"],
                "name": f"DH Lottery Add-on ({username})",
                "manufacturer": "DH Lottery",
                "model": "Add-on",
                "sw_version": "2.0.0",
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
            payload = json.dumps(config)
            result = self.client.publish(discovery_topic, payload, qos=1, retain=True)
            result.wait_for_publish()
            _LOGGER.debug(f"Published discovery for {sensor_id}: {discovery_topic}")
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
        state_topic = f"homeassistant/sensor/dhlottery_addon_{username}_{sensor_id}/state"
        
        try:
            # Publish state
            result = self.client.publish(state_topic, str(state), qos=1, retain=True)
            result.wait_for_publish()
            
            # Publish attributes if provided
            if attributes:
                attr_topic = f"homeassistant/sensor/dhlottery_addon_{username}_{sensor_id}/attributes"
                attr_payload = json.dumps(attributes)
                result = self.client.publish(attr_topic, attr_payload, qos=1, retain=True)
                result.wait_for_publish()
            
            _LOGGER.debug(f"Published state for {sensor_id}: {state}")
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
        
        discovery_topic = f"homeassistant/sensor/dhlottery_addon_{username}_{sensor_id}/config"
        
        try:
            result = self.client.publish(discovery_topic, "", qos=1, retain=True)
            result.wait_for_publish()
            _LOGGER.info(f"Removed sensor: {sensor_id}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to remove sensor {sensor_id}: {e}")
            return False
    
    def publish_button_discovery(
        self,
        button_id: str,
        name: str,
        command_topic: str,
        username: str,
        icon: Optional[str] = None,
        device_class: Optional[str] = None,
    ) -> bool:
        """
        Publish button discovery configuration
        
        Args:
            button_id: Button ID (e.g., 'buy_auto_1', 'buy_auto_all')
            name: Friendly name
            command_topic: MQTT topic for commands
            username: DH Lottery username
            icon: Icon (e.g., 'mdi:ticket-confirmation')
            device_class: Device class (e.g., 'restart')
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Discovery topic: homeassistant/button/dhlottery_addon_USERNAME_BUTTON_ID/config
        discovery_topic = f"homeassistant/button/dhlottery_addon_{username}_{button_id}/config"
        
        # Unique ID: dhlottery_addon_USERNAME_BUTTON_ID
        unique_id = f"dhlottery_addon_{username}_{button_id}"
        
        # Entity ID: button.dhlottery_addon_USERNAME_BUTTON_ID
        object_id = f"dhlottery_addon_{username}_{button_id}"
        
        config = {
            "name": name,
            "unique_id": unique_id,
            "default_entity_id": f"button.{object_id}",
            "command_topic": command_topic,
            "device": {
                "identifiers": [f"dhlottery_addon_{username}"],
                "name": f"DH Lottery Add-on ({username})",
                "manufacturer": "DH Lottery",
                "model": "Add-on",
                "sw_version": "2.0.0",
            },
        }
        
        # Optional fields
        if icon:
            config["icon"] = icon
        if device_class:
            config["device_class"] = device_class
        
        try:
            payload = json.dumps(config)
            _LOGGER.debug(f"Publishing button discovery: {discovery_topic}")
            _LOGGER.debug(f"Config: {payload}")
            result = self.client.publish(discovery_topic, payload, qos=1, retain=True)
            result.wait_for_publish()
            _LOGGER.info(f"✅ Published button discovery: button.{object_id}")
            return True
        except Exception as e:
            _LOGGER.error(f"❌ Failed to publish button discovery for {button_id}: {e}")
            return False
    
    def subscribe_to_commands(self, username: str, callback) -> bool:
        """
        Subscribe to button command topics
        
        Args:
            username: DH Lottery username
            callback: Callback function to handle messages
        """
        if not self.connected:
            _LOGGER.warning("Not connected to MQTT broker")
            return False
        
        # Subscribe to all button command topics
        command_topic = f"homeassistant/button/dhlottery_addon_{username}_+/command"
        
        try:
            result = self.client.subscribe(command_topic)
            self.client.on_message = callback
            _LOGGER.info(f"✅ Subscribed to button commands: {command_topic}")
            _LOGGER.info(f"📡 Waiting for button press events...")
            return True
        except Exception as e:
            _LOGGER.error(f"❌ Failed to subscribe to commands: {e}")
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
    state_topic = f"homeassistant/sensor/dhlottery_addon_{username}_{entity_id}/state"
    
    # Prepare attributes topic
    json_attributes_topic = None
    if attributes:
        json_attributes_topic = f"homeassistant/sensor/dhlottery_addon_{username}_{entity_id}/attributes"
    
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
    return mqtt_client.publish_sensor_state(
        sensor_id=entity_id,
        username=username,
        state=state,
        attributes=attributes
    )
