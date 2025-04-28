from paho.mqtt import client as mqtt
from handlers.config import TOPICS
import numpy as np
from sensor_data_struct_pb2 import IMUData, OdometryData, LidarScan

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "validator")

coppelia_client = "coppelia"
agv_client = "agv"

latest_data = {
    coppelia_client: {},
    agv_client: {}
}

first_scan_received = {
    coppelia_client: False,
    agv_client: False,
}

lidar_params = {
    coppelia_client: None,
    agv_client: None,
}

lidar_params_checked = False  # <- Flag global para checar uma única vez

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
        for topic in TOPICS:
            coppelia_topic = topic.replace("CLIENT", coppelia_client)
            client.subscribe(coppelia_topic)
            print(f"Subscribed to: {coppelia_topic}")

            agv_topic = topic.replace("CLIENT", agv_client)
            client.subscribe(agv_topic)
            print(f"Subscribed to: {agv_topic}")
    else:
        print("Failed to connect, return code %d\n", reason_code)

def on_disconnect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Disconnected from MQTT Broker!")
    elif reason_code > 0:
        print("Unexpected disconnection, return code %d\n", reason_code)

def on_message(client, userdata, msg):
    global lidar_params_checked

    if msg.topic.startswith(coppelia_client):
        source = coppelia_client
    elif msg.topic.startswith(agv_client):
        source = agv_client
    else:
        return

    topic_suffix = msg.topic.split("/", 1)[1]

    try:
        if "imu/linearVelocity" in topic_suffix:
            sensor_data = IMUData()
            sensor_data.ParseFromString(msg.payload)
            values = list(sensor_data.linear_velocity)
            latest_data[source][topic_suffix] = values

        elif "imu/angularVelocity" in topic_suffix:
            sensor_data = IMUData()
            sensor_data.ParseFromString(msg.payload)
            values = list(sensor_data.angular_velocity)
            latest_data[source][topic_suffix] = values

        elif "odometry/pose" in topic_suffix:
            sensor_data = OdometryData()
            sensor_data.ParseFromString(msg.payload)
            values = list(sensor_data.pose)
            latest_data[source][topic_suffix] = values

        elif "odometry/wheel_vel" in topic_suffix:
            sensor_data = OdometryData()
            sensor_data.ParseFromString(msg.payload)
            values = list(sensor_data.wheel_velocities)
            latest_data[source][topic_suffix] = values

        elif "sensor/ranges" in topic_suffix:
            sensor_data = LidarScan()
            sensor_data.ParseFromString(msg.payload)

            latest_data[source]["sensor/ranges"] = list(sensor_data.ranges)
            latest_data[source]["sensor/intensities"] = list(sensor_data.intensities)

            if not first_scan_received[source]:
                lidar_params[source] = {
                    "angle_min": sensor_data.angle_min,
                    "angle_max": sensor_data.angle_max,
                    "angle_increment": sensor_data.angle_increment,
                    "range_min": sensor_data.range_min,
                    "range_max": sensor_data.range_max,
                }
                first_scan_received[source] = True

            if (first_scan_received[coppelia_client] and first_scan_received[agv_client] and not lidar_params_checked):
                ref_params = lidar_params[coppelia_client]
                test_params = lidar_params[agv_client]
                for key in ref_params:
                    if abs(ref_params[key] - test_params[key]) > 1e-6:
                        print(f"[WARNING] Lidar parameter {key} mismatch: {ref_params[key]} vs {test_params[key]}")
                lidar_params_checked = True

        else:
            print(f"Unknown topic suffix: {topic_suffix}")
            return

    except Exception as e:
        print(f"Failed to parse Protobuf payload from topic {msg.topic}: {e}")
        return

    other_source = agv_client if source == coppelia_client else coppelia_client

    if topic_suffix != "sensor/ranges":
        if topic_suffix in latest_data[other_source]:
            ref = latest_data[coppelia_client][topic_suffix]
            test = latest_data[agv_client][topic_suffix]
            mse = compute_mse(ref, test)
            print(f"[MSE] {topic_suffix}: {mse:.6f}")
    else:
        if "sensor/ranges" in latest_data[other_source]:
            ref = latest_data[coppelia_client]["sensor/ranges"]
            test = latest_data[agv_client]["sensor/ranges"]
            mse = compute_mse(ref, test)
            print(f"[MSE] sensor/ranges: {mse:.6f}")

        if "sensor/intensities" in latest_data[other_source]:
            ref = latest_data[coppelia_client]["sensor/intensities"]
            test = latest_data[agv_client]["sensor/intensities"]
            mse = compute_mse(ref, test)
            print(f"[MSE] sensor/intensities: {mse:.6f}")

def compute_mse(ref, test):
    try:
        ref_array = np.array(ref, dtype=np.float32)
        test_array = np.array(test, dtype=np.float32)

        if ref_array.shape != test_array.shape:
            min_len = min(len(ref_array), len(test_array))
            ref_array = ref_array[:min_len]
            test_array = test_array[:min_len]

        mse = np.mean((ref_array - test_array) ** 2)
        return mse
    except Exception as e:
        print(f"Error computing MSE: {e}")
        return float('inf')

if __name__ == "__main__":
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    client.connect("localhost", 1883)
    client.loop_forever()
