import sys
import time
import openvr
from math import sqrt, copysign

def matrixToXYZ(matrix):
	pose = {}
	# From http://steamcommunity.com/app/358720/discussions/0/358417008714224220/#c359543542244499836
	position = {}
	position['x'] = matrix[0][3]
	position['y'] = matrix[1][3]
	position['z'] = matrix[2][3]
	q = {}
	
	#Turn matrix into quaternions
	q['w'] = sqrt(max(0, 1 + matrix[0][0] + matrix[1][1] + matrix[2][2])) / 2.0
	q['x'] = sqrt(max(0, 1 + matrix[0][0] - matrix[1][1] - matrix[2][2])) / 2.0
	q['y'] = sqrt(max(0, 1 - matrix[0][0] + matrix[1][1] - matrix[2][2])) / 2.0
	q['z'] = sqrt(max(0, 1 - matrix[0][0] - matrix[1][1] + matrix[2][2])) / 2.0
	
	#Turn matrix into XYZ
	q['x'] = copysign(q['x'], matrix[2][1] - matrix[1][2])
	q['y'] = copysign(q['y'], matrix[0][2] - matrix[2][0])
	q['z'] = copysign(q['z'], matrix[1][0] - matrix[0][1])
	
	#Save to dictionary
	pose['position'] = position
	pose['orientation'] = q
	
	return pose

openvr.init(openvr.VRApplication_Scene)

poses = []  # Let waitGetPoses populate the poses structure the first time

# Print converted XYZ and Quaternion rotation 100 times
for i in range(100):
    poses, game_poses = openvr.VRCompositor().waitGetPoses(poses, None)
    hmd_pose = poses[openvr.k_unTrackedDeviceIndex_Hmd]
    xyz = matrixToXYZ(hmd_pose.mDeviceToAbsoluteTracking)
    print(xyz)
    sys.stdout.flush()
    time.sleep(0.2)

openvr.shutdown()
