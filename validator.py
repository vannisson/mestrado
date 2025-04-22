from paho.mqtt import client as mqtt
from handlers.config import TOPICS
import json
import numpy as np

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "validator")

coppelia_client = "coppelia"
agv_client = "agv"

# Store latest messages for each source
latest_data = {
    coppelia_client: {},
    agv_client: {}
}

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")

        for topic in TOPICS:
            # Simulation topic
            coppelia_topic = topic.replace("CLIENT", coppelia_client)
            client.subscribe(coppelia_topic)
            print(f"Subscribed to: {coppelia_topic}")

            # Real AGV topic
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
    # Determine the source of the message
    if msg.topic.startswith(coppelia_client):
        source = coppelia_client
    elif msg.topic.startswith(agv_client):
        source = agv_client
    else:
        return

    # Extract the topic suffix
    topic_suffix = msg.topic.split("/", 1)[1]

    try:
        # Parse the string into a list of floats
        values = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        try:
            values = eval(msg.payload.decode())
        except Exception:
            print(f"Failed to parse payload from topic {msg.topic}")
            return

    # Store the message
    latest_data[source][topic_suffix] = values

    # Check if we have data from both sources for the same topic
    other_source = agv_client if source == coppelia_client else coppelia_client
    if topic_suffix in latest_data[other_source]:
        ref = latest_data[coppelia_client][topic_suffix]
        test = latest_data[agv_client][topic_suffix]
        mse = compute_mse(ref, test)
        print(f"[MSE] {topic_suffix}: {mse:.6f}")

def compute_mse(ref, test):
    """Compute Mean Squared Error between two lists"""
    try:
        ref_array = np.array(ref, dtype=np.float32)
        test_array = np.array(test, dtype=np.float32)

        # Ensure same length
        if ref_array.shape != test_array.shape:
            min_len = min(len(ref_array), len(test_array))
            ref_array = ref_array[:min_len]
            test_array = test_array[:min_len]

        mse = np.mean((ref_array - test_array) ** 2)
        return mse
    except Exception as e:
        print(f"Error computing MSE: {e}")
        return float('inf')

# Entry point for the script
if __name__ == "__main__":
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    client.connect("localhost", 1883)
    client.loop_forever()
