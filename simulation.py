import math

def sysCall_init():
    """ Initialization function for the robot and Velodyne LIDAR """
    sim = require('sim')
    simVision = require('simVision')

    global motorLeft, motorRight, lidar_handle, detect, braitenbergL, braitenbergR, v0, ptCloud

    # Get motor handles
    motorLeft = sim.getObject("../leftMotor")
    motorRight = sim.getObject("../rightMotor")

    # Get vision sensors for Velodyne
    visionSensorHandles = [sim.getObject(f"../sensor[{i}]") for i in range(4)]
    ptCloud = sim.getObject("../ptCloud")

    # Velodyne VPL-16 parameters
    frequency = 5  # 5 Hz
    options = 2 + 8  # Display settings
    pointSize = 2
    coloring_closeAndFarDistance = [1, 4]
    displayScaling = 0.999

    # Create Velodyne sensor and store handle
    lidar_handle = simVision.createVelodyneVPL16(
        visionSensorHandles, frequency, options, pointSize, coloring_closeAndFarDistance, displayScaling, ptCloud
    )
    if lidar_handle is None:
        print("Error: Velodyne initialization failed!")

    # Braitenberg algorithm settings
    v0 = 2  # Base speed
    detect = [0] * 16  # Simulated 16 virtual sensors from LIDAR

    # Braitenberg behavior weights
    braitenbergL = [-0.2, -0.4, -0.6, -0.8, -1, -1.2, -1.4, -1.6,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    braitenbergR = [-1.6, -1.4, -1.2, -1, -0.8, -0.6, -0.4, -0.2,  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

def process_lidar_data():
    """ Captures LIDAR data and simulates 16 virtual sensors """

    if lidar_handle is None:
        print("Error: Invalid LIDAR handle!")
        return [0] * 16  # Return default empty detection

    # Retrieve point cloud data using the Velodyne sensor
    raw_data = simVision.handleVelodyneVPL16(lidar_handle + sim.handleflag_abscoords, sim.getSimulationTimeStep())

    if not raw_data:
        return [0] * 16  # If no points detected, return default array

    # Sample fewer points to reduce computation time (process every 5th point)
    distances = [math.sqrt(raw_data[i]**2 + raw_data[i+1]**2 + raw_data[i+2]**2) 
                 for i in range(0, len(raw_data), 15)]  # Processing fewer points

    # Detection range thresholds
    noDetectionDist = 0.5  # Maximum distance where objects are ignored
    maxDetectionDist = 0.2  # Minimum distance where objects are fully detected

    # Define the number of virtual sectors for obstacle detection
    num_sectors = 16
    sector_values = [0] * num_sectors

    # Get LIDAR's current orientation
    lidar_orientation = sim.getObjectOrientation(lidar_handle, -1)[2] * 180 / 3.1415  

    # Map each LIDAR point to its corresponding sector
    for d in distances:
        angle = lidar_orientation  
        sector_index = int((angle + 180) / (360 / num_sectors))
        if 0 <= sector_index < num_sectors:
            if d < noDetectionDist:
                if d < maxDetectionDist:
                    d = maxDetectionDist  
                sector_values[sector_index] = 1 - ((d - maxDetectionDist) / (noDetectionDist - maxDetectionDist))

    return sector_values


def sysCall_sensing():
    """ Handles point cloud visualization (optional) """
    global ptCloud

    # Retrieve LIDAR data (processing at lower frequency)
    if sim.getSimulationTime() % 1 == 0:  # Process every second (or choose another interval)
        data = simVision.handleVelodyneVPL16(lidar_handle + sim.handleflag_abscoords, sim.getSimulationTimeStep())

        # If we want to display the detected points ourselves:
        if ptCloud:
            sim.removePointsFromPointCloud(ptCloud, 0, None, 0)
        else:
            ptCloud = sim.createPointCloud(0.02, 20, 0, 2)  # Create a point cloud object

        sim.insertPointsIntoPointCloud(ptCloud, 0, data)


def sysCall_actuation():
    """ Applies Braitenberg logic to avoid obstacles """
    global detect
    detect = process_lidar_data()

    vLeft = v0
    vRight = v0

    for i in range(16):
        vLeft += braitenbergL[i] * detect[i]
        vRight += braitenbergR[i] * detect[i]

    sim.setJointTargetVelocity(motorLeft, vLeft)
    sim.setJointTargetVelocity(motorRight, vRight)


def sysCall_cleanup():
    """ Cleans up Velodyne resources when simulation stops """
    simVision.destroyVelodyneVPL16(lidar_handle)
