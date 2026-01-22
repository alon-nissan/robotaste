from pump_controller import (
    BurstCommandBuilder,
    PumpBurstConfig,
    NE4000Pump,
)

config_0 = PumpBurstConfig(
    address=0, rate_ul_min=60000, volume_ul=3000, diameter_mm=29.0, direction="INF"
)
config_1 = PumpBurstConfig(
    address=1, rate_ul_min=30000, volume_ul=1000, diameter_mm=29.0, direction="INF"
)

commnads = BurstCommandBuilder.build_burst_commands([config_0])
asdf = True
pump0 = NE4000Pump(port="/dev/cu.PL2303G-USBtoUART120", address=0)
pump0.connect()
config_response = pump0._send_burst_command(commnads.config_command)
validation_response = pump0._send_burst_command(commnads.validation_command)
run_response = pump0._send_burst_command(commnads.run_command)
asdf = True
