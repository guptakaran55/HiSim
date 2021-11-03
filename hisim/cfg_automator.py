import json
import os
import ast
import component
import inspect
import shutil
import sys
import loadtypes
import globals as gb
import numpy as np
from inspect import isclass
from pkgutil import iter_modules
from pathlib import Path as gg
from importlib import import_module

# IMPORT ALL COMPONENT CLASSES DYNAMICALLY
# DIRTY CODE. GIVE ME BETTER SUGGESTIONS

# iterate through the modules in the current package
package_dir = os.path.join(gg(__file__).resolve().parent, "components")

for (_, module_name, _) in iter_modules([package_dir]):

    # import the module and iterate through its attributes
    module = import_module(f"components.{module_name}")
    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)

        if isclass(attribute):
            # Add the class to this package's variables
            globals()[attribute_name] = attribute


from globals import HISIMPATH
import simulator

__authors__ = "Vitor Hugo Bellotto Zago"
__copyright__ = "Copyright 2021, the House Infrastructure Project"
__credits__ = ["Noah Pflugradt"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Vitor Hugo Bellotto Zago"
__email__ = "vitor.zago@rwth-aachen.de"
__status__ = "development"


def get_subclasses(classname=None):
    """
    Return a list of all the children classes
    in this module from parent class classname
    """
    list_of_children = [cls.__name__ for cls in classname.__subclasses__()]
    return list_of_children

class ConfigurationGenerator:
    SimulationParameters = {"year": 2019,
                            "seconds_per_timestep": 60,
                            "method": "full_year"}

    def __init__(self, set=None):
        self.data = {}
        self.components = {}
        self.load_component_modules()
        self.add_sim_param()

    def load_component_modules(self):
        def get_default_parameters_from_constructor(cls):
            """
            Get the default argument of either a function or
            a class

            :param obj: a function or class
            :param parameter:
            :return: a dictionary or list of the arguments
            """
            class_component = globals()[cls]
            constructor_function_var = [item for item in inspect.getmembers(class_component) if item[0] in "__init__"][0][1]
            sig = inspect.signature(constructor_function_var)
            return {k: v.default for k, v in sig.parameters.items() if
                            v.default is not inspect.Parameter.empty}

        component_class_children = get_subclasses(component.Component)
        for component_class in component_class_children:
            default_args = get_default_parameters_from_constructor(component_class)

            # Remove the simulation parameters of the list
            if "sim_params" in default_args:
                del default_args["sim_params"]

            # Save every component in the dictionary attribute
            self.components[component_class] = default_args

    def add_sim_param(self):
        self.data["SimulationParameters"] = self.SimulationParameters

    def dump(self):
        with open(HISIMPATH["cfg"], "w") as f:
            json.dump(self.data, f, indent=4)

    def add_component(self, user_components_name):
        if isinstance(user_components_name, list):
            for user_component_name in user_components_name:
                self.data[user_component_name] = self.components[user_component_name]
        else:
            self.data[user_components_name] = self.components[user_components_name]

    def print_components(self):
        print(json.dumps(self.components, sort_keys=True, indent=4))

    def print_component(self, name):
        print(json.dumps(self.components[name], sort_keys=True, indent=4))




class SmartHome:

    def __init__(self, function=None, mode=None):
        if os.path.isfile(HISIMPATH["cfg"]):
            with open(os.path.join(HISIMPATH["cfg"])) as file:
                cfg = json.load(file)
            self.cfg = cfg
        else:
            self.cfg = None
        self.function = function
        self.mode = mode
        self.electricity_grids : List[ElectricityGrid] = []
        self.electricity_grid_consumption : List[ElectricityGrid] = []

    def build(self, my_sim):
        if self.cfg is not None:
            for component in self.cfg["Order"]:

                if component == "SimulationParameters":
                    self.add_sim_param(my_sim)
                if component == "Weather":
                    #command = "self.add_{}(my_sim)".format(component.lower())
                    self.add_weather(my_sim)
                if component == "Occupancy":
                    self.add_occupancy(my_sim)
                if component == "PVSystem":
                    self.add_pvs(my_sim)
                if component == "Building":
                    self.add_building(my_sim)
                if component == "HeatPump":
                    self.add_heat_pump(my_sim)
                if component == "EVCharger":
                    self.add_ev_charger(my_sim)
                if component == "Battery":
                    self.add_battery(my_sim)
                if component == "FlexibilityController":
                    self.add_flexibility(my_sim)
                if component == "ThermalEnergyStorage":
                    self.add_thermal_energy_storage(my_sim)
                if component == "Dummy":
                    self.add_dummy(my_sim)
                if component == "AdvancedBattery":
                    self.add_advanced_battery(my_sim)
                if component == "Controller":
                    self.add_advanced_battery(my_sim)
            self.close(my_sim)
        else:
            raise Exception("No configuration file!")

    def add_sim_param(self, my_sim):
        # Timeline configuration
        method = self.cfg["SimulationParameters"]["method"]
        self.cfg["SimulationParameters"].pop("method", None)
        if method == "full_year":
            self.time: simulator.SimulationParameters = simulator.SimulationParameters.full_year(**self.cfg["SimulationParameters"])
        elif method == "one_day_only":
            self.time: simulator.SimulationParameters = simulator.SimulationParameters.one_day_only(**self.cfg["SimulationParameters"])
        my_sim.set_parameters(self.time)

    def add_weather(self, my_sim):
        # Sets Weather
        self.weather = Weather(**self.cfg["Weather"])
        my_sim.add_component(self.weather)

    def add_occupancy(self, my_sim):
        # Sets Occupancy
        self.occupancy = Occupancy(**self.cfg["Occupancy"])
        my_sim.add_component(self.occupancy)
        self.add_to_electricity_grid_consumption(my_sim, self.occupancy)

    def add_pvs(self, my_sim):
        # Sets PV System
        self.pvs = PVSystem(**self.cfg["PVSystem"], sim_params=self.time)
        self.pvs.connect_similar_inputs(self.weather)
        my_sim.add_component(self.pvs)

        # Sets base grid with PVSystem
        #self.electricity_grids.append(ElectricityGrid(name="BaseloadAndPVSystem", grid=[self.occupancy, "Subtract", self.pvs]))
        #my_sim.add_component(self.electricity_grids[-1])

    def add_building(self, my_sim):
        # Sets Residence
        self.building = Building(**self.cfg["Building"], sim_params=self.time)
        self.building.connect_similar_inputs([self.weather, self.occupancy])
        my_sim.add_component(self.building)

    def basic_setup(self, my_sim):
        self.add_sim_param(my_sim)
        self.add_csv_load_power(my_sim)
        self.add_weather(my_sim)
        #self.add_occupancy(my_sim)
        self.add_pvs(my_sim)
        #self.add_building(my_sim)

    def add_heat_pump(self, my_sim):
        # Sets Heat Pump
        self.heat_pump = HeatPump(**self.cfg["HeatPump"], sim_params=self.time)

        # Sets Heat Pump Controller
        self.heat_pump_controller = HeatPumpController(**self.cfg["HeatPumpController"])

        self.building.connect_similar_inputs([self.heat_pump])
        #my_sim.add_component(self.building)
        #self.dummy.connect_similar_inputs([self.heat_pump])

        self.heat_pump.connect_similar_inputs([self.weather, self.heat_pump_controller])
        my_sim.add_component(self.heat_pump)

        self.heat_pump_controller.connect_similar_inputs(self.building)
        #self.heat_pump_controller.connect_similar_inputs(self.dummy)
        self.heat_pump_controller.connect_electricity(self.electricity_grids[-1])
        my_sim.add_component(self.heat_pump_controller)

        self.add_to_electricity_grid_consumption(my_sim, self.heat_pump)
        self.add_to_electricity_grid(my_sim, self.heat_pump)

    def add_to_electricity_grid(self, my_sim, next_component, electricity_grid_label=None):
        n_consumption_components = len(self.electricity_grids)
        if electricity_grid_label is None:
            electricity_grid_label = "Load{}".format(n_consumption_components)
        if n_consumption_components == 0:
            list_components = [next_component]
        else:
            list_components = [self.electricity_grids[-1], "Sum", next_component]
        self.electricity_grids.append(ElectricityGrid(name=electricity_grid_label, grid=list_components))
        #self.electricity_grids.append(self.electricity_grids[-1]+next_component)
        my_sim.add_component(self.electricity_grids[-1])
        #if hasattr(next_component, "type"):
        #    if next_component.type == "Consumer":
        #        self.add_to_electricity_grid_consumption(my_sim, next_component)

    def add_to_electricity_grid_consumption(self, my_sim, next_component, electricity_grid_label = None):
        n_consumption_components = len(self.electricity_grid_consumption)
        if electricity_grid_label is None:
            electricity_grid_label = "Consumption{}".format(n_consumption_components)
        if n_consumption_components == 0:
            list_components = [next_component]
        else:
            list_components = [self.electricity_grid_consumption[-1], "Sum", next_component]
        self.electricity_grid_consumption.append(ElectricityGrid(name=electricity_grid_label, grid=list_components))
        my_sim.add_component(self.electricity_grid_consumption[-1])

    def add_ev_charger(self, my_sim):
        # Sets Electric Vehicle
        self.my_electric_vehicle = Vehicle_Pure(**self.cfg["Vehicle_Pure"])

        # Sets EV Charger Controller
        self.ev_charger_controller = EVChargerController(**self.cfg["EVChargerController"])

        # Sets EV Charger
        self.ev_charger = EVCharger(**self.cfg["EVCharger"],
                                    electric_vehicle=self.my_electric_vehicle,
                                    sim_params=self.time)

        #########################################################################################################
        self.ev_charger_controller.connect_electricity(self.electricity_grids[-1])
        self.ev_charger_controller.connect_similar_inputs(self.ev_charger)
        my_sim.add_component(self.ev_charger_controller)

        self.ev_charger.connect_electricity(self.electricity_grids[-1])
        self.ev_charger.connect_similar_inputs(self.ev_charger_controller)
        my_sim.add_component(self.ev_charger)

        self.add_to_electricity_grid_consumption(my_sim, self.ev_charger)
        self.add_to_electricity_grid(my_sim, self.ev_charger)

    def add_flexibility(self, my_sim):
        self.flexible_controller = Controller(**self.cfg["FlexibilityController"])
        self.controllable = Controllable()

        if int(self.cfg["FlexibilityController"]["mode"]) == 1:
            self.flexible_controller.connect_electricity(self.electricity_grids[0])
        else:
            self.flexible_controller.connect_electricity(self.electricity_grids[-1])
        my_sim.add_component(self.flexible_controller)

        self.controllable.connect_similar_inputs(self.flexible_controller)
        my_sim.add_component(self.controllable)

        self.add_to_electricity_grid_consumption(my_sim, self.controllable)
        self.add_to_electricity_grid(my_sim, self.controllable)

    def add_dummy(self, my_sim):

        self.dummy = Dummy(**self.cfg["Dummy"], sim_params=self.time)
        my_sim.add_component(self.dummy)

        self.add_to_electricity_grid_consumption(my_sim, self.dummy)
        self.add_to_electricity_grid(my_sim, self.dummy)

    def add_battery(self, my_sim):

        self.battery_controller = BatteryController()

        self.battery_controller.connect_electricity(self.electricity_grids[-1])
        my_sim.add_component(self.battery_controller)

        self.battery = Battery(**self.cfg["Battery"], sim_params=self.time)
        self.battery.connect_similar_inputs(self.battery_controller)
        self.battery.connect_electricity(self.electricity_grids[-1])
        my_sim.add_component(self.battery)

        self.add_to_electricity_grid_consumption(my_sim, self.battery)
        self.add_to_electricity_grid(my_sim, self.battery)


    def add_advanced_battery(self,my_sim):

        self.advanced_battery = AdvancedBattery(**self.cfg["AdvancedBattery"],sim_params=my_sim)

        my_sim.add_component(self.advanced_battery)

    def add_csv_load_power(self,my_sim):
        self.csv_load_power_demand = CSVLoader(component_name="csv_load_power",
                                          csv_filename="Lastprofile/SOSO/Orginal/EFH_Bestand_TRY_5_Profile_1min.csv",
                                          column=0,
                                          loadtype=loadtypes.LoadTypes.Electricity,
                                          unit=loadtypes.Units.Watt,
                                          column_name="power_demand",
                                          simulation_parameters=my_sim,
                                          multiplier=6)
        my_sim.add_component(self.csv_load_power_demand)

    def add_controller(self,my_sim):

        self.controller = Controller()
        self.controller.connect_input(self.controller.ElectricityToOrFromBatteryReal,
                                    self.advanced_battery.ComponentName,
                                    self.advanced_battery.ACBatteryPower)
        self.controller.connect_input(self.controller.ElectricityConsumptionBuilding,
                                    self.csv_load_power_demand.ComponentName,
                                    self.csv_load_power_demand.Output1)
        self.controller.connect_input(self.controller.ElectricityOutputPvs,
                                    self.pvs.ComponentName,
                                    self.pvs.ElectricityOutput)
        my_sim.add_component(self.controller)

        self.advanced_battery.connect_input(self.advanced_battery.LoadingPowerInput,
                                            self.controller.ComponentName,
                                            self.controller.ElectricityToOrFromBatteryTarget)
    def add_thermal_energy_storage(self, my_sim):
        wws_c = WarmWaterStorageConfig()
        self.tes = ThermalEnergyStorage2(component_name="MyStorage", config=wws_c, sim_params=self.time)

        # storage
        self.tes.connect_input(self.tes.HeatPump_ChargingSideInput_mass, self.heat_pump.ComponentName, self.heat_pump.WaterOutput_mass)
        self.tes.connect_input(self.tes.HeatPump_ChargingSideInput_temperature, self.heat_pump.ComponentName, self.heat_pump.WaterOutput_temperature)

        #self.tes.connect_input(self.tes.Heating_DischargingSideInput_mass, householdheatdemand.ComponentName, householdheatdemand.MassOutput)
        #self.tes.connect_input(self.tes.Heating_DischargingSideInput_temperature, householdheatdemand.ComponentName, householdheatdemand.TemperatureOutput)
        self.tes.connect_input(self.tes.WW_DischargingSideInput_mass, self.occupancy.ComponentName, self.occupancy.WW_MassOutput)
        self.tes.connect_input(self.tes.WW_DischargingSideInput_temperature, self.occupancy.ComponentName, self.occupancy.WW_TemperatureOutput)


        self.occupancy.connect_input(self.occupancy.WW_MassInput, self.tes.ComponentName, self.tes.WW_DischargingSideOutput_mass)
        self.occupancy.connect_input(self.occupancy.WW_TemperatureInput, self.tes.ComponentName, self.tes.WW_DischargingSideOutput_temperature)

        self.heat_pump.connect_input(self.heat_pump.WaterConsumption, self.occupancy.ComponentName, self.occupancy.WaterConsumption)
        self.heat_pump.connect_input(self.heat_pump.WaterInput_mass, self.tes.ComponentName, self.tes.HeatPump_ChargingSideOutput_mass)
        self.heat_pump.connect_input(self.heat_pump.WaterInput_temperature, self.tes.ComponentName, self.tes.HeatPump_ChargingSideOutput_temperature)

        my_sim.add_component(self.tes)

    def close(self, my_sim):
        pass
        #my_last_grid = ElectricityGrid(name="Consumed", grid=[self.electricity_grid_consumption[-1]])
        #my_sim.add_component(my_last_grid)
        #my_final_grid_positive = ElectricityGrid(name="NotConveredConsumed", grid=[self.electricity_grids[-1]], signal="Positive")
        #my_sim.add_component(my_final_grid_positive)

if __name__ == "__main__":
    delete_all_results()


    #component_class = get_subclasses(component.Component)
    #sig = get_default_args(globals()[component_class[3]], "__init__")
    #args = get_default_args(sig)
    #print(args)
    #print()
