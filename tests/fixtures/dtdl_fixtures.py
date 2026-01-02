"""
DTDL test fixtures for the test suite.

Contains various DTDL content samples for testing the DTDL parser,
validator, and converter functionality.
"""

# =============================================================================
# Simple DTDL Interfaces
# =============================================================================

SIMPLE_DTDL_INTERFACE = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Thermostat;1",
    "@type": "Interface",
    "displayName": "Thermostat",
    "contents": [
        {
            "@type": "Property",
            "name": "targetTemperature",
            "schema": "double"
        },
        {
            "@type": "Telemetry",
            "name": "currentTemperature",
            "schema": "double"
        }
    ]
}

DTDL_WITH_RELATIONSHIP = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Room;1",
    "@type": "Interface",
    "displayName": "Room",
    "contents": [
        {
            "@type": "Property",
            "name": "name",
            "schema": "string"
        },
        {
            "@type": "Relationship",
            "name": "hasThermostat",
            "target": "dtmi:com:example:Thermostat;1"
        }
    ]
}

DTDL_WITH_ENUM = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Device;1",
    "@type": "Interface",
    "displayName": "Device",
    "contents": [
        {
            "@type": "Property",
            "name": "status",
            "schema": {
                "@type": "Enum",
                "valueSchema": "string",
                "enumValues": [
                    {"name": "online", "enumValue": "ONLINE"},
                    {"name": "offline", "enumValue": "OFFLINE"},
                    {"name": "maintenance", "enumValue": "MAINTENANCE"}
                ]
            }
        }
    ]
}

DTDL_WITH_TELEMETRY = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Sensor;1",
    "@type": "Interface",
    "displayName": "Sensor",
    "contents": [
        {
            "@type": "Telemetry",
            "name": "temperature",
            "schema": "double",
            "unit": "degreeCelsius"
        },
        {
            "@type": "Telemetry",
            "name": "humidity",
            "schema": "double",
            "unit": "percent"
        },
        {
            "@type": "Telemetry",
            "name": "pressure",
            "schema": "double"
        }
    ]
}

DTDL_WITH_COMPONENT = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Machine;1",
    "@type": "Interface",
    "displayName": "Machine",
    "contents": [
        {
            "@type": "Property",
            "name": "serialNumber",
            "schema": "string"
        },
        {
            "@type": "Component",
            "name": "thermostat",
            "schema": "dtmi:com:example:Thermostat;1"
        }
    ]
}

DTDL_WITH_INHERITANCE = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:SmartThermostat;1",
    "@type": "Interface",
    "displayName": "Smart Thermostat",
    "extends": "dtmi:com:example:Thermostat;1",
    "contents": [
        {
            "@type": "Property",
            "name": "wifiEnabled",
            "schema": "boolean"
        },
        {
            "@type": "Property",
            "name": "firmwareVersion",
            "schema": "string"
        }
    ]
}


# =============================================================================
# Complex DTDL Interfaces
# =============================================================================

DTDL_ARRAY_OF_OBJECTS = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Factory;1",
    "@type": "Interface",
    "displayName": "Factory",
    "contents": [
        {
            "@type": "Property",
            "name": "name",
            "schema": "string"
        },
        {
            "@type": "Property",
            "name": "workers",
            "schema": {
                "@type": "Array",
                "elementSchema": {
                    "@type": "Object",
                    "fields": [
                        {"name": "employeeId", "schema": "string"},
                        {"name": "name", "schema": "string"},
                        {"name": "role", "schema": "string"}
                    ]
                }
            }
        }
    ]
}

DTDL_NESTED_OBJECTS = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Building;1",
    "@type": "Interface",
    "displayName": "Building",
    "contents": [
        {
            "@type": "Property",
            "name": "address",
            "schema": {
                "@type": "Object",
                "fields": [
                    {"name": "street", "schema": "string"},
                    {"name": "city", "schema": "string"},
                    {"name": "country", "schema": "string"},
                    {
                        "name": "coordinates",
                        "schema": {
                            "@type": "Object",
                            "fields": [
                                {"name": "latitude", "schema": "double"},
                                {"name": "longitude", "schema": "double"}
                            ]
                        }
                    }
                ]
            }
        }
    ]
}


# =============================================================================
# DTDL V3 specific features
# =============================================================================

DTDL_V3_INTERFACE = {
    "@context": "dtmi:dtdl:context;3",
    "@id": "dtmi:com:example:SensorV3;1",
    "@type": "Interface",
    "displayName": "Sensor V3",
    "description": "A sensor using DTDL v3 features",
    "contents": [
        {
            "@type": "Property",
            "name": "temperature",
            "schema": "double"
        },
        {
            "@type": "Command",
            "name": "reset",
            "description": "Resets the sensor"
        }
    ]
}


# =============================================================================
# Edge case DTDL content
# =============================================================================

DTDL_EMPTY_INTERFACE = {
    "@context": "dtmi:dtdl:context;4",
    "@id": "dtmi:com:example:Empty;1",
    "@type": "Interface",
    "displayName": "Empty",
    "contents": []
}

DTDL_MULTIPLE_INTERFACES = [
    {
        "@context": "dtmi:dtdl:context;4",
        "@id": "dtmi:com:example:Device1;1",
        "@type": "Interface",
        "displayName": "Device 1",
        "contents": [
            {"@type": "Property", "name": "prop1", "schema": "string"}
        ]
    },
    {
        "@context": "dtmi:dtdl:context;4",
        "@id": "dtmi:com:example:Device2;1",
        "@type": "Interface",
        "displayName": "Device 2",
        "contents": [
            {"@type": "Property", "name": "prop2", "schema": "integer"}
        ]
    }
]
