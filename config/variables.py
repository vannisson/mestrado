BROKER = "localhost"
PORT = 1883
CONTROL_TOPIC = "fleet_manager/cmd_vel"
VALIDATION_TOPICS = [
    "CLIENT/imu/linearVelocity",
    "CLIENT/imu/angularVelocity",
    "CLIENT/odometry/pose",
    "CLIENT/odometry/wheel_vel",
    "CLIENT/sensor/ranges",
]