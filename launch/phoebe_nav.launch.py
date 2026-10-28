#!/usr/bin/env python3
#
# Copyright (c) 2025, United States Government, as represented by the
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
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.actions import IncludeLaunchDescription, GroupAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import PythonExpression
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from launch_ros.parameter_descriptions import ParameterFile


def generate_launch_description():
    pkg_phoebe_nav2_config = get_package_share_directory("phoebe_nav2_config")
    pkg_phoebe_deploy = get_package_share_directory("phoebe_deploy")

    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument(
            "namespace",
            default_value="",
            description="Namespace for the robot.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tf_prefix",
            default_value="",
            description="Prefix for tf frames and joint names. Must match the robot description and controllers.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "launch_rviz",
            default_value="true",
            description="Launch rviz or nah",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "rviz_config_file",
            default_value=PathJoinSubstitution(
                [get_package_share_directory("phoebe_nav2_config"), "rviz", "nav2.rviz"]
            ),
            description="Full path to an rviz config file for bringup",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="false",
            description="Use the simulation clock. Also selects the sim defaults for mode and nav2_config_file.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "publish_tf",
            default_value="True",
            description="Publish map -> odom (from slam_toolbox or AMCL) and odom -> base_link (from the EKF). "
            "If false, handle these transforms elsewhere.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "magic_carpet",
            default_value="false",
            description="Use ground-truth odometry from the sim magic carpet. Skips AMCL, slam_toolbox and the EKF.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "mode",
            default_value=PythonExpression(
                ["'localization' if '", LaunchConfiguration("use_sim_time"), "' == 'true' else 'mapping'"]
            ),
            choices=["localization", "mapping"],
            description="localization: AMCL against map. mapping: slam_toolbox. Defaults to localization in sim, "
            "mapping on hardware. Ignored with magic_carpet.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "map",
            default_value=PathJoinSubstitution([pkg_phoebe_nav2_config, "config", "maps", "phoebe_sim_env.yaml"]),
            description="Map yaml for the global costmap and AMCL. Defaults to the sim map.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "nav2_config_file",
            default_value=PathJoinSubstitution(
                [
                    pkg_phoebe_nav2_config,
                    "config",
                    PythonExpression(
                        [
                            "'clearpath_nav2_config_sim.yaml' if '",
                            LaunchConfiguration("use_sim_time"),
                            "' == 'true' else 'clearpath_nav2_config.yaml'",
                        ]
                    ),
                ]
            ),
            description="Nav2 params yaml, including the amcl block. Defaults to the sim config in sim.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "ekf_config_file",
            default_value=PathJoinSubstitution([pkg_phoebe_nav2_config, "config", "localization.yaml"]),
            description="robot_localization EKF params yaml.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "slam_config_file",
            default_value=PathJoinSubstitution([pkg_phoebe_nav2_config, "config", "clearpath_slam_config.yaml"]),
            description="slam_toolbox params yaml for mode:=mapping, used when publish_tf is true. "
            "Otherwise the packaged no-tf config is used.",
        )
    )

    namespace = LaunchConfiguration("namespace")
    tf_prefix = LaunchConfiguration("tf_prefix")
    launch_rviz = LaunchConfiguration("launch_rviz")
    rviz_config_file = LaunchConfiguration("rviz_config_file")
    use_sim_time = LaunchConfiguration("use_sim_time")
    publish_tf = LaunchConfiguration("publish_tf")
    magic_carpet = LaunchConfiguration("magic_carpet")
    mode = LaunchConfiguration("mode")
    map_yaml_file = LaunchConfiguration("map")
    nav2_config_file = LaunchConfiguration("nav2_config_file")
    ekf_config_file = LaunchConfiguration("ekf_config_file")
    slam_config_file = LaunchConfiguration("slam_config_file")

    rviz_qss_file = PathJoinSubstitution([get_package_share_directory("phoebe_nav2_config"), "config", "dark.qss"])

    is_localization_mode = PythonExpression(["'", mode, "' == 'localization'"])
    is_mapping_mode = PythonExpression(["'", mode, "' == 'mapping'"])

    nodes_to_start = [
        # AMCL/mapping are both skipped in magic carpet mode. Instead we rely on the magic
        # carpet controller to connect odom -> base_link, and a static transform publisher in
        # place of localization.
        GroupAction(
            condition=UnlessCondition(magic_carpet),
            actions=[
                # If using localization, run AMCL against the static map and map server. Note that we do not have
                # a hardware map, so this is only relevant for sim.
                GroupAction(
                    condition=IfCondition(is_localization_mode),
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                [PathJoinSubstitution([pkg_phoebe_nav2_config, "launch", "localization.launch.py"])]
                            ),
                            launch_arguments={
                                "namespace": "",
                                "tf_prefix": tf_prefix,
                                "use_sim_time": use_sim_time,
                                "map": map_yaml_file,
                                "params_file": nav2_config_file,
                                "use_amcl": "true",
                                "publish_tf": publish_tf,
                            }.items(),
                        ),
                    ],
                ),
                # Mapping mode will build a new map with slam_toolbox instead of localizing.
                # TODO: This is not actually tested on HW yet
                GroupAction(
                    condition=IfCondition(is_mapping_mode),
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                [PathJoinSubstitution([pkg_phoebe_nav2_config, "launch", "online_async_launch.py"])]
                            ),
                            launch_arguments={
                                "tf_prefix": tf_prefix,
                                "slam_params_file": slam_config_file,
                                "use_sim_time": use_sim_time,
                            }.items(),
                            condition=IfCondition(publish_tf),
                        ),
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                [PathJoinSubstitution([pkg_phoebe_nav2_config, "launch", "online_async_launch.py"])]
                            ),
                            launch_arguments={
                                "tf_prefix": tf_prefix,
                                "slam_params_file": PathJoinSubstitution(
                                    [pkg_phoebe_nav2_config, "config/clearpath_slam_config_no_tf.yaml"]
                                ),
                                "use_sim_time": use_sim_time,
                            }.items(),
                            condition=UnlessCondition(publish_tf),
                        ),
                    ],
                ),
            ],
        ),
        # Magic carpet still needs map_server for the global costmap's static layer, but no AMCL.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [PathJoinSubstitution([pkg_phoebe_nav2_config, "launch", "localization.launch.py"])]
            ),
            launch_arguments={
                "namespace": "",
                "tf_prefix": tf_prefix,
                "use_sim_time": use_sim_time,
                "map": map_yaml_file,
                "params_file": nav2_config_file,
                "use_amcl": "false",
            }.items(),
            condition=IfCondition(magic_carpet),
        ),
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="map_to_odom_identity",
            arguments=["0", "0", "0", "0", "0", "0", [tf_prefix, "map"], [tf_prefix, "odom"]],
            parameters=[{"use_sim_time": use_sim_time}],
            condition=IfCondition(magic_carpet),
        ),
        # Use custom nav launch file for tf prefixing fix
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [PathJoinSubstitution([(pkg_phoebe_nav2_config), "launch", "navigation_launch.py"])]
            ),
            launch_arguments={
                "namespace": "",
                "tf_prefix": tf_prefix,
                "params_file": nav2_config_file,
                "use_sim_time": use_sim_time,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [PathJoinSubstitution([(pkg_phoebe_deploy), "launch", "ridgeback_sensors.launch.py"])]
            ),
            launch_arguments={
                "namespace": "",
                "tf_prefix": tf_prefix,
                "is_sim": use_sim_time,
            }.items(),
            condition=UnlessCondition(magic_carpet),
        ),
        # Fuses wheel odometry and the IMU into odom -> base_link and ridgeback/odometry/filtered.
        Node(
            package="robot_localization",
            executable="ekf_node",
            name="ekf_node",
            namespace="ridgeback",
            output="screen",
            parameters=[
                ParameterFile(ekf_config_file, allow_substs=True),
                {"use_sim_time": use_sim_time, "publish_tf": publish_tf},
            ],
            remappings=[
                ("~/odometry/filtered", "platform/odom/filtered"),
                ("~/diagnostics", "diagnostics"),
                ("~/tf", "tf"),
                ("~/tf_static", "tf_static"),
            ],
            condition=UnlessCondition(magic_carpet),
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2_nav2",
            output="log",
            arguments=["-d", rviz_config_file, "--stylesheet", rviz_qss_file],
            condition=IfCondition(launch_rviz),
            parameters=[{"use_sim_time": use_sim_time}],
        ),
        Node(
            package="phoebe_deploy",
            executable="world_publisher.py",
            name="world_publisher",
            parameters=[
                {
                    "use_sim_time": use_sim_time,
                    "rate_hz": 30,
                    "map_frame": [tf_prefix, "map"],
                }
            ],
        ),
        # Launch the odom to joint state publisher if needed for other planning applications.
        Node(
            package="phoebe_deploy",
            executable="odometry_joint_state_publisher.py",
            name="odometry_joint_state_publisher",
            parameters=[{"use_sim_time": use_sim_time}],
            condition=UnlessCondition(publish_tf),
        ),
    ]

    # Namespaces are pushed down by this group action, so don't namespace anything directly
    # above or you end up with duplicates.
    ns_action = GroupAction(
        actions=[
            PushRosNamespace(namespace),
            SetRemap(src="tf_static", dst="/tf_static"),
            SetRemap(src="tf", dst="/tf"),
        ]
        + nodes_to_start
    )

    return LaunchDescription(declared_arguments + [ns_action])
