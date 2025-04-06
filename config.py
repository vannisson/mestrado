
CLIENT_NAME = "pioneer"

TOPICS = [
    # IMU
    f"{CLIENT_NAME}/imu/linearVelocity",
    f"{CLIENT_NAME}/imu/angularVelocity",
    # Odometry
    f"{CLIENT_NAME}/odometry/pose",
    f"{CLIENT_NAME}/odometry/wheel_vel",
    # Sensor
    f"{CLIENT_NAME}/sensor/ranges",
    f"{CLIENT_NAME}/sensor/intensities",
]