# Remko IR

Home Assistant custom integration for controlling a Remko RKL 495 portable air conditioner through a universal Zigbee IR remote.

## Development

Home Assistant currently requires Python 3.14. Run this repository from an isolated local virtual environment. Do not reuse a Home Assistant Core development environment, because its editable `homeassistant` package can shadow the released version used by the custom-component test harness.

Create a local virtual environment and install the development dependencies:

```bash
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_test.txt
```

Run the local checks from the repository root:

```bash
python -m compileall -q custom_components
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

The same commands are available as the **Test Remko IR** and **Lint Remko IR** tasks in VS Code.

## Install in Home Assistant

Copy or symlink `custom_components/remko_ir` into the Home Assistant configuration directory:

```bash
ln -s /path/to/remko_ir/custom_components/remko_ir \
  /path/to/home-assistant/config/custom_components/remko_ir
```

Ensure the Zigbee2MQTT IR remote is configured first, then add **Remko IR** through Home Assistant's integration setup. Enter the remote's MQTT command topic, for example `zigbee2mqtt/living_room_ir/set`.

The integration publishes IR commands to that topic with the Zigbee2MQTT payload `{"ir_code_to_send": "..."}`.

The supported target temperature range is 16-30 C.

The integration currently maintains assumed state because IR commands do not provide feedback from the air conditioner.
