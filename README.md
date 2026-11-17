
# eQ-3 MAX! Integration for Home Assistant

A feature-rich custom integration for the **eQ-3 MAX! heating system**, bringing your MAX! Cube and connected heating devices into Home Assistant.

The integration provides native Home Assistant device management, climate entities, sensors, advanced thermostat configuration and a dedicated custom card for managing weekly heating schedules.

No YAML configuration is required.

---

## Features

### MAX! Cube integration

- Connect Home Assistant to your MAX! Cube through your local network.
- Configure the Cube directly from the Home Assistant UI.
- No YAML configuration required.
- Enable or disable the integration on the fly.
- Native Home Assistant Config Flow.
<img width="660" height="500" alt="image" src="https://github.com/user-attachments/assets/eab3c8f0-6d44-49ed-b456-365af23c5b76" />


### Native device management

Every MAX! thermostat is represented as an individual Home Assistant device.

The integration automatically organizes devices and their entities, providing a clean and intuitive interface.
<img width="690" height="438" alt="image" src="https://github.com/user-attachments/assets/c58d6d6c-9590-4ce0-9332-9894d6cecedd" />


### Climate entities and sensors

Each thermostat exposes a native Climate entity, together with additional sensors for monitoring its status.

Available information includes:

- Full climate entity
- Valve position.
<img width="966" height="530" alt="image" src="https://github.com/user-attachments/assets/5d7bc884-1fc8-452f-a15a-fcb89ec5cbeb" />

### Advanced thermostat configuration

The integration exposes almost all configurable thermostat parameters directly in Home Assistant.

Depending on the device, these include:

- Boost duration.
- Boost valve position.
- Comfort temperature.
- Eco temperature.
- Maximum and minimum temperature.
- Maximum valve position.
- Temperature offset.
- Valve offset.
- Window-open duration and temperature.
- Descaling day and time.

These settings are accessible through Home Assistant entities, without needing the original MAX! software.
<img width="345" height="831" alt="image" src="https://github.com/user-attachments/assets/8d011fc7-3aaf-4bd1-b16c-e7f9bc88b2a7" />

### Diagnostic information

Additional diagnostic entities provide useful information about each thermostat and its operating conditions.

Examples include:

- Battery status.
- Connection and link quality.
- RF address.
- Room information.
<img width="946" height="896" alt="image" src="https://github.com/user-attachments/assets/af62ba1f-c84a-4e3f-8258-34422e689e4c" />

### Weekly heating programs – MAX! Custom Card

One of the most useful features is the dedicated **MAX! Custom Card**, designed to visualize and manage the weekly heating schedules of your thermostats directly from the Home Assistant dashboard.

The card provides an intuitive graphical representation of the entire weekly schedule.

Features include:

- Weekly overview of programmed temperatures.
- Individual daily schedule visualization.
- Graphical time and temperature intervals.
- Selection and editing of individual time slots.
- Adding and removing schedule intervals.
- Copying schedules between days.
- Quick copy options for Monday–Friday, Saturday–Sunday or the entire week.
- Saving changes directly to the MAX! device.

The weekly schedule can be managed directly from your Home Assistant dashboard, without using the original MAX! application.

<img width="982" height="960" alt="image" src="https://github.com/user-attachments/assets/8e91fb8a-9882-42ec-a9a0-2f2abaaf023b" />


---

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant.
2. Navigate to **Integrations**.
3. Open the three-dot menu and select **Custom repositories**.
4. Add the following repository:

   `https://github.com/MassiPi/MAX`

5. Select **Integration** as the category.
6. Add the repository.
7. Find **MAX** in HACS and install it.
8. Restart Home Assistant.

### Manual installation

1. Download this repository.
2. Copy the `custom_components/max` directory into your Home Assistant configuration directory.

The resulting structure should look like this:

```text
config/
└── custom_components/
    └── max/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        └── ...
```

3. Restart Home Assistant.

---

## Configuration

After installing the integration:

1. Go to **Settings → Devices & Services**.
2. Click **Add Integration**.
3. Search for **MAX**.
4. Enter the IP address of your MAX! Cube.
5. Enter the connection port (default: `62910`).
6. Complete the setup.

The integration will connect to the Cube and discover the available devices.

No YAML configuration is required.

---

## Background and development

This project started in October 2023 as a review and improvement of the original Home Assistant integration for the ELV/eQ-3 MAX! heating system.

At that time, the MAX! cloud services had already been discontinued, but the local MAX! Cube communication was still working reliably.

The original integration and its underlying Python library had several limitations and bugs, and no active maintainer was available.

Rather than abandoning a perfectly usable heating system, this project aimed to fix the existing implementation and extend its capabilities.

The initial improvements included:

- Fixed Cube-level command transmission.
- Improved handling of device data.
- Added device link-quality binary sensors.
- Added valve opening sensors.
- Extended thermostat attributes.
- Improved preset handling, including Window Open.
- Extended Window Open functionality to wall thermostats.
- Extended programmed-temperature retrieval to wall thermostats.

Over time, the project evolved beyond the original integration.

The architecture was completely reorganized around Home Assistant's Config Flow and native device management, introducing:

- Graphical integration setup.
- Runtime enable/disable support.
- Individual device organization.
- Extended thermostat configuration entities.
- Additional diagnostic entities.
- A dedicated MAX! Custom Card for weekly heating schedule management.

The goal remains the same: keep the eQ-3 MAX! ecosystem alive and make it a fully integrated part of modern Home Assistant installations.

---

## Requirements

- Home Assistant.
- An eQ-3 MAX! Cube.
- A working local network connection between Home Assistant and the MAX! Cube.

## Community and support

For discussions, questions, feedback and development updates, visit the original Home Assistant Community thread:

https://community.home-assistant.io/t/eq-3-max-integration/628530

For bug reports and feature requests, use the GitHub repository:

https://github.com/MassiPi/MAX

## Disclaimer

This is an independent community-maintained custom integration.

It is not affiliated with, endorsed by or supported by eQ-3 or ELV.

MAX! is a trademark of its respective owner.
