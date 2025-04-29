VALIDATION_TOPICS = [
    # IMU
    "CLIENT/imu/linearVelocity",
    "CLIENT/imu/angularVelocity",
    # Odometry
    "CLIENT/odometry/pose",
    "CLIENT/odometry/wheel_vel",
    # Sensor
    "CLIENT/sensor/ranges",
    # "CLIENT/sensor/intensities",
]

CONTROL_TOPIC = "CLIENT/cmd_vel"

BROKER = "localhost"

PORT = 1883