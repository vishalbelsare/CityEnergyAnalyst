import json
import os

import numpy as np
import pandas as pd
from py4design import py3dmodel, py2radiance

__author__ = "Jimeno A. Fonseca"
__copyright__ = "Copyright 2017, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Jimeno A. Fonseca", "Kian Wee Chen"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"

from cea.constants import HOURS_IN_YEAR
from cea.resources.radiation_daysim.geometry_generator import BuildingGeometry
from cea import suppress_3rd_party_debug_loggers

suppress_3rd_party_debug_loggers()


def create_sensor_input_file(rad, chunk_n):
    sensor_file_path = os.path.join(rad.data_folder_path, "points_" + str(chunk_n) + ".pts")
    sensor_file = open(sensor_file_path, "w")
    sensor_pts_data = py2radiance.write_rad.sensor_file(rad.sensor_positions, rad.sensor_normals)
    sensor_file.write(sensor_pts_data)
    sensor_file.close()
    rad.sensor_file_path = sensor_file_path


def generate_sensor_surfaces(occface, wall_dim, roof_dim, srf_type, orientation, normal, intersection):
    mid_pt = py3dmodel.calculate.face_midpt(occface)
    location_pt = py3dmodel.modify.move_pt(mid_pt, normal, 0.01)
    moved_oface = py3dmodel.fetch.topo2topotype(py3dmodel.modify.move(mid_pt, location_pt, occface))
    if srf_type == 'roofs':
        xdim = ydim = roof_dim
    else:
        xdim = ydim = wall_dim
    # put it into occ and subdivide surfaces
    sensor_surfaces = py3dmodel.construct.grid_face(moved_oface, xdim, ydim)

    # calculate list of properties per surface
    sensor_intersection = [intersection for x in sensor_surfaces]
    sensor_dir = [normal for x in sensor_surfaces]
    sensor_cord = [py3dmodel.calculate.face_midpt(x) for x in sensor_surfaces]
    sensor_type = [srf_type for x in sensor_surfaces]
    sensor_orientation = [orientation for x in sensor_surfaces]
    sensor_area = [py3dmodel.calculate.face_area(x) * (1.0 - scalar)
                   for x, scalar in zip(sensor_surfaces, sensor_intersection)]

    return sensor_dir, sensor_cord, sensor_type, sensor_area, sensor_orientation, sensor_intersection


def calc_sensors_building(building_geometry, grid_size):
    sensor_dir_list = []
    sensor_cord_list = []
    sensor_type_list = []
    sensor_area_list = []
    sensor_orientation_list = []
    sensor_intersection_list = []
    surfaces_types = ['walls', 'windows', 'roofs']
    sensor_vertical_grid_dim = grid_size["walls_grid"]
    sensor_horizontal_grid_dim = grid_size["roof_grid"]
    for srf_type in surfaces_types:
        occface_list = getattr(building_geometry, srf_type)
        if srf_type == 'roofs':
            orientation_list = ['top'] * len(occface_list)
            normals_list = [(0.0, 0.0, 1.0)] * len(occface_list)
            interesection_list = [0] * len(occface_list)
        elif srf_type == 'windows':
            orientation_list = getattr(building_geometry, "orientation_{srf_type}".format(srf_type=srf_type))
            normals_list = getattr(building_geometry, "normals_{srf_type}".format(srf_type=srf_type))
            interesection_list = [0] * len(occface_list)
        else:
            orientation_list = getattr(building_geometry, "orientation_{srf_type}".format(srf_type=srf_type))
            normals_list = getattr(building_geometry, "normals_{srf_type}".format(srf_type=srf_type))
            interesection_list = getattr(building_geometry, "intersect_{srf_type}".format(srf_type=srf_type))
        for orientation, normal, face, intersection in zip(orientation_list, normals_list, occface_list,
                                                           interesection_list):
            sensor_dir, \
            sensor_cord, \
            sensor_type, \
            sensor_area, \
            sensor_orientation, \
            sensor_intersection = generate_sensor_surfaces(face,
                                                           sensor_vertical_grid_dim,
                                                           sensor_horizontal_grid_dim,
                                                           srf_type,
                                                           orientation,
                                                           normal,
                                                           intersection)
            sensor_intersection_list.extend(sensor_intersection)
            sensor_dir_list.extend(sensor_dir)
            sensor_cord_list.extend(sensor_cord)
            sensor_type_list.extend(sensor_type)
            sensor_area_list.extend(sensor_area)
            sensor_orientation_list.extend(sensor_orientation)

    return sensor_dir_list, sensor_cord_list, sensor_type_list, sensor_area_list, sensor_orientation_list, sensor_intersection_list


def calc_sensors_zone(building_names, locator, grid_size, geometry_pickle_dir):
    sensors_coords_zone = []
    sensors_dir_zone = []
    sensors_total_number_list = []
    names_zone = []
    sensors_code_zone = []
    sensor_intersection_zone = []
    for building_name in building_names:
        building_geometry = BuildingGeometry.load(os.path.join(geometry_pickle_dir, 'zone', building_name))
        # get sensors in the building
        sensors_dir_building, \
        sensors_coords_building, \
        sensors_type_building, \
        sensors_area_building, \
        sensor_orientation_building, \
        sensor_intersection_building = calc_sensors_building(building_geometry, grid_size)

        # get the total number of sensors and store in lst
        sensors_number = len(sensors_coords_building)
        sensors_total_number_list.append(sensors_number)

        sensors_code = ['srf' + str(x) for x in range(sensors_number)]
        sensors_code_zone.append(sensors_code)

        # get the total list of coordinates and directions to send to daysim
        sensors_coords_zone.extend(sensors_coords_building)
        sensors_dir_zone.extend(sensors_dir_building)

        # get total list of intersections
        sensor_intersection_zone.append(sensor_intersection_building)

        # get the name of all buildings
        names_zone.append(building_name)

        # save sensors geometry result to disk
        pd.DataFrame({'BUILDING': building_name,
                      'SURFACE': sensors_code,
                      'orientation': sensor_orientation_building,
                      'intersection': sensor_intersection_building,
                      'Xcoor': [x[0] for x in sensors_coords_building],
                      'Ycoor': [x[1] for x in sensors_coords_building],
                      'Zcoor': [x[2] for x in sensors_coords_building],
                      'Xdir': [x[0] for x in sensors_dir_building],
                      'Ydir': [x[1] for x in sensors_dir_building],
                      'Zdir': [x[2] for x in sensors_dir_building],
                      'AREA_m2': sensors_area_building,
                      'TYPE': sensors_type_building}).to_csv(locator.get_radiation_metadata(building_name), index=False)

    return sensors_coords_zone, sensors_dir_zone, sensors_total_number_list, names_zone, sensors_code_zone, sensor_intersection_zone


def isolation_daysim(chunk_n, cea_daysim, building_names, locator, radiance_parameters, write_sensor_data, grid_size,
                     max_global, weatherfile, geometry_pickle_dir):
    # initialize daysim project
    daysim_project = cea_daysim.initialize_daysim_project('chunk_{n}'.format(n=chunk_n))
    print('Creating daysim project in: {daysim_dir}'.format(daysim_dir=daysim_project.project_path))

    # calculate sensors
    print("Calculating and sending sensor points")
    sensors_coords_zone, \
    sensors_dir_zone, \
    sensors_number_zone, \
    names_zone, \
    sensors_code_zone, \
    sensor_intersection_zone = calc_sensors_zone(building_names, locator, grid_size, geometry_pickle_dir)

    num_sensors = sum(sensors_number_zone)
    daysim_project.create_sensor_input_file(sensors_coords_zone, sensors_dir_zone, num_sensors, "w/m2")

    print(f"Starting Daysim simulation for buildings: {names_zone}")
    print(f"Total number of sensors: {num_sensors}")

    print('Writing radiance parameters')
    daysim_project.write_radiance_parameters(**radiance_parameters)

    print('Executing hourly solar isolation calculation')
    daysim_project.execute_gen_dc()
    daysim_project.execute_ds_illum()

    print('Reading results...')
    solar_res = daysim_project.eval_ill()

    # check inconsistencies and replace by max value of weather file
    print('Fixing inconsistencies, if any')
    solar_res = np.clip(solar_res, a_min=0.0, a_max=max_global)

    # Check if leap year and remove extra day
    if solar_res.shape[1] == HOURS_IN_YEAR + 24:
        print('Removing leap day')
        leap_day_hours = range(1416, 1440)
        solar_res = np.delete(solar_res, leap_day_hours, axis=1)

    print("Writing results to disk")
    index = 0
    for building_name, sensors_number, sensor_code, sensor_intersection \
            in zip(names_zone, sensors_number_zone, sensors_code_zone, sensor_intersection_zone):

        # select sensors data
        sensor_data = solar_res[index:index+sensors_number]
        # set sensors that intersect with buildings to 0
        sensor_data[np.array(sensor_intersection) == 1] = 0
        items_sensor_name_and_result = pd.DataFrame(sensor_data, index=sensor_code)

        # create summary and save to disk
        date = weatherfile["date"]
        write_aggregated_results(building_name, items_sensor_name_and_result, locator, date)

        if write_sensor_data:
            sensor_data_path = locator.get_radiation_building_sensors(building_name)
            write_sensor_results(sensor_data_path, items_sensor_name_and_result)

        # Increase sensor index
        index = index + sensors_number

    # erase daysim folder to avoid conflicts after every iteration
    print('Removing results folder')
    daysim_project.cleanup_project()


def write_sensor_results(sensor_data_path, sensor_values):
    with open(sensor_data_path, 'w') as outfile:
        json.dump(sensor_values.T.to_dict(orient="list"), outfile)


def write_aggregated_results(building_name, sensor_values, locator, date):
    # Get sensor properties
    geometry = pd.read_csv(locator.get_radiation_metadata(building_name)).set_index('SURFACE')

    # Create map between sensors and building surfaces
    labels = geometry['TYPE'] + '_' + geometry['orientation']
    group_dict = labels.to_dict()

    # Transform data
    sensor_values_kw = sensor_values.multiply(geometry['AREA_m2'], axis="index") / 1000
    data = sensor_values_kw.groupby(group_dict).sum().T.add_suffix('_kW')

    # TODO: Remove total sensor area information from output. Area information is repeated over rows.
    # Add area to data
    area = geometry['AREA_m2'].groupby(group_dict).sum().add_suffix('_m2')
    area_cols = pd.concat([area] * len(data), axis=1).T.set_index(data.index)
    data = pd.concat([data, area_cols], axis=1)

    # Round values and add date index
    data = data.round(2)
    data["Date"] = date
    data.set_index("Date", inplace=True)

    data.to_csv(locator.get_radiation_building(building_name))
