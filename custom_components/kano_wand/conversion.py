import math


class WandConversion:
    def __init__(self, x, y):
        self.canvas = {
            "x": x,
            "y": y,
        }
        self.matrix = [
            1,
            0,
            0,
            0,
            0,
            1,
            0,
            0,
            0,
            0,
            1,
            0,
            0,
            0,
            0,
            1,
        ]
        self.zero_vector = {"x": 0, "y": 0, "z": 0}
        self.one_vector = {"x": 1, "y": 1, "z": 1}
        self.euler = {
            "x": 0,
            "y": 0,
            "z": 0,
        }

    def position(self, quat):
        quaternion = [v / 1024 for v in quat]
        norm_quaternion = self.normalize(quaternion)
        matrix_rotated_from_quat = self.make_rotation_from_quaternion(
            self.zero_vector, norm_quaternion, self.one_vector, self.matrix
        )
        yaw, roll, pitch = self.set_from_rotation_matrix(matrix_rotated_from_quat)
        yaw_complete = self.yaw_complete(yaw, pitch)
        x, y = self.get_xy(yaw, pitch)
        return {
            "x": x,
            "y": y,
            "pitch": pitch / 2,
            "roll": -roll,
            "yaw": yaw_complete,
        }

    def get_xy(self, y, p):
        w = self.canvas["x"] / 2
        h = self.canvas["y"] / 2
        return [-(((y / 180) * (w * 4)) - w), h - (3 * p)]

    @staticmethod
    def normalize(quat):
        length = WandConversion.quat_length(quat)
        x, y, z, w = quat
        if length == 0:
            x, y, z, w = 0, 0, 0, 1
        else:
            length = 1 / length
            x *= length
            y *= length
            z *= length
            w *= length
        return {
            "x": x,
            "y": y,
            "z": z,
            "w": w,
        }

    @staticmethod
    def quat_length(quat):
        return math.sqrt(quat[1] ** 2 + quat[2] ** 2 + quat[3] ** 2 + quat[0] ** 2)

    @staticmethod
    def set_from_rotation_matrix(matrix):
        matrix11, matrix12, matrix13 = matrix[0], matrix[4], matrix[8]
        matrix22, matrix23 = matrix[5], matrix[9]
        matrix32, matrix33 = matrix[6], matrix[10]
        y = math.asin(WandConversion.clamp(matrix13, -1, 1))
        if abs(matrix13) < 0.99999:
            x = math.atan2(-matrix23, matrix33)
            z = math.atan2(-matrix12, matrix11)
        else:
            x = math.atan2(matrix32, matrix22)
            z = 0
        return [
            WandConversion.to_real(WandConversion.to_degrees(angle))
            for angle in [y, z, x * 2]
        ]

    @staticmethod
    def make_rotation_from_quaternion(position, quaternion, scale, matrix):
        x, y, z, w = quaternion["x"], quaternion["y"], quaternion["z"], quaternion["w"]
        xx = x * (x + x)
        xy = x * (y + y)
        xz = x * (z + z)
        yy = y * (y + y)
        yz = y * (z + z)
        zz = z * (z + z)
        wx = w * (x + x)
        wy = w * (y + y)
        wz = w * (z + z)
        sx = scale["x"]
        sy = scale["y"]
        sz = scale["z"]

        matrix[0] = (1 - (yy + zz)) * sx
        matrix[1] = (xy + wz) * sx
        matrix[2] = (xz - wy) * sx
        matrix[3] = 0
        matrix[4] = (xy - wz) * sy
        matrix[5] = (1 - (xx + zz)) * sy
        matrix[6] = (yz + wx) * sy
        matrix[7] = 0
        matrix[8] = (xz + wy) * sz
        matrix[9] = (yz - wx) * sz
        matrix[10] = (1 - (xx + yy)) * sz
        matrix[11] = 0
        matrix[12] = position["x"]
        matrix[13] = position["y"]
        matrix[14] = position["z"]
        matrix[15] = 1
        return matrix

    @staticmethod
    def clamp(value, min_val, max_val):
        return max(min_val, min(max_val, value))

    @staticmethod
    def yaw_complete(yaw, pitch):
        if pitch > 180 or pitch < -180:
            yaw_complete = 180 - (-yaw)
        else:
            yaw_complete = -yaw
        return yaw_complete

    @staticmethod
    def to_degrees(angle):
        return angle * (180 / math.pi)

    @staticmethod
    def to_radian(angle):
        return angle * (math.pi / 180)

    @staticmethod
    def to_real(x):
        try:
            return float(format(float(x), ".1f"))
        except ValueError:
            return x

    @staticmethod
    def map(n, start1, stop1, start2, stop2):
        return (((n - start1) / (stop1 - start1)) * (stop2 - start2)) + start2

    @staticmethod
    def arr_multiply(array, num1, num2):
        return array[num1] * array[num2]

    @staticmethod
    def distance(x1, x2, y1, y2):
        return math.sqrt(((x2 - x1) ** 2) + ((y2 - y1) ** 2))
