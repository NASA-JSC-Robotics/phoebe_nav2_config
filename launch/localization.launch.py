#!/usr/bin/env python3
#
# Copyright (c) 2026, United States Government, as represented by the
# Administrator of the National Aeronautics and Space Administration.
#
# All rights reserved.
#
# This software is licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace, SetParameter
from launch_ros.parameter_descriptions import ParameterFile


def generate_launch_description():
    pkg_phoebe_nav2_config = get_package_share_directory("phoebe_nav2_config")

    declared_arguments = [
        DeclareLaunchArgument("namespace", default_value="", description="Top-level namespace"),
        DeclareLaunchArgument(
            "tf_prefix",
            default_value="",
            description="tf_prefix applied to frame ids referenced by params_file and map_server's frame_id.",
        ),
        DeclareLaunchArgument("use_sim_time", default_value="false", description="Use simulation clock if true"),
        DeclareLaunchArgument(
            "map",
            default_value=PathJoinSubstitution([pkg_phoebe_nav2_config, "config", "maps", "phoebe_sim_env.yaml"]),
            description="Full path to the map yaml file for map_server.",
        ),
        DeclareLaunchArgument(
            "params_file",
            default_value=PathJoinSubstitution([pkg_phoebe_nav2_config, "config", "clearpath_nav2_config.yaml"]),
            description="Full path to the yaml file containing the amcl: params block.",
        ),
        DeclareLaunchArgument(
            "use_amcl",
            default_value="true",
            description="Run AMCL. Disable in magic carpet mode, where ground-truth odometry is used instead.",
        ),
        DeclareLaunchArgument(
            "publish_tf",
            default_value="True",
            description="AMCL's tf_broadcast - whether it publishes map -> odom.",
        ),
        DeclareLaunchArgument("autostart", default_value="true", description="Automatically startup map_server/amcl"),
        DeclareLaunchArgument(
            "use_respawn", default_value="False", description="Whether to respawn map_server if it crashes."
        ),
        DeclareLaunchArgument("log_level", default_value="info", description="log level"),
    ]

    namespace = LaunchConfiguration("namespace")
    tf_prefix = LaunchConfiguration("tf_prefix")
    use_sim_time = LaunchConfiguration("use_sim_time")
    map_yaml_file = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")
    use_amcl = LaunchConfiguration("use_amcl")
    publish_tf = LaunchConfiguration("publish_tf")
    autostart = LaunchConfiguration("autostart")
    use_respawn = LaunchConfiguration("use_respawn")
    log_level = LaunchConfiguration("log_level")

    amcl_params = ParameterFile(params_file, allow_substs=True)

    localization = GroupAction(
        actions=[
            PushRosNamespace(namespace),
            SetParameter("use_sim_time", use_sim_time),
            Node(
                package="nav2_map_server",
                executable="map_server",
                name="map_server",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[{"yaml_filename": map_yaml_file, "frame_id": [tf_prefix, "map"]}],
                arguments=["--ros-args", "--log-level", log_level],
            ),
            Node(
                package="nav2_amcl",
                executable="amcl",
                name="amcl",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[amcl_params, {"tf_broadcast": publish_tf}],
                arguments=["--ros-args", "--log-level", log_level],
                condition=IfCondition(use_amcl),
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_localization",
                output="screen",
                arguments=["--ros-args", "--log-level", log_level],
                # map_server must be configured/activated before amcl - amcl's on_configure
                # needs the map, and lifecycle_manager transitions nodes in list order.
                parameters=[{"autostart": autostart, "node_names": ["map_server", "amcl"]}],
                condition=IfCondition(use_amcl),
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_localization",
                output="screen",
                arguments=["--ros-args", "--log-level", log_level],
                parameters=[{"autostart": autostart, "node_names": ["map_server"]}],
                condition=UnlessCondition(use_amcl),
            ),
        ],
    )

    return LaunchDescription(declared_arguments + [localization])
