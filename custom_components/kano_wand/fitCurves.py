import math


class Maths:
    @staticmethod
    def zeros_Xx2x2(x):
        return [[0, 0] for _ in range(x)]

    @staticmethod
    def mulItems(items, multiplier):
        return [items[0] * multiplier, items[1] * multiplier]

    @staticmethod
    def mulMatrix(m1, m2):
        return m1[0] * m2[0] + m1[1] * m2[1]

    @staticmethod
    def subtract(arr1, arr2):
        return [arr1[0] - arr2[0], arr1[1] - arr2[1]]

    @staticmethod
    def addArrays(arr1, arr2):
        return [arr1[0] + arr2[0], arr1[1] + arr2[1]]

    @staticmethod
    def addItems(items, addition):
        return [items[0] + addition, items[1] + addition]

    @staticmethod
    def sum(items):
        return sum(items)

    @staticmethod
    def dot(m1, m2):
        return Maths.mulMatrix(m1, m2)

    @staticmethod
    def vectorLen(v):
        a, b = v
        return math.sqrt(a * a + b * b)

    @staticmethod
    def divItems(items, divisor):
        if divisor == 0:
            return [0.0, 0.0]
        return [items[0] / divisor, items[1] / divisor]

    @staticmethod
    def squareItems(items):
        a, b = items
        return [a * a, b * b]

    @staticmethod
    def normalize(v):
        return Maths.divItems(v, Maths.vectorLen(v))


class Bezier:
    @staticmethod
    def q(ctrlPoly, t):
        tx = 1.0 - t
        pA = Maths.mulItems(ctrlPoly[0], tx * tx * tx)
        pB = Maths.mulItems(ctrlPoly[1], 3 * tx * tx * t)
        pC = Maths.mulItems(ctrlPoly[2], 3 * tx * t * t)
        pD = Maths.mulItems(ctrlPoly[3], t * t * t)
        return Maths.addArrays(Maths.addArrays(pA, pB), Maths.addArrays(pC, pD))

    @staticmethod
    def qprime(ctrlPoly, t):
        tx = 1.0 - t
        pA = Maths.mulItems(Maths.subtract(ctrlPoly[1], ctrlPoly[0]), 3 * tx * tx)
        pB = Maths.mulItems(Maths.subtract(ctrlPoly[2], ctrlPoly[1]), 6 * tx * t)
        pC = Maths.mulItems(Maths.subtract(ctrlPoly[3], ctrlPoly[2]), 3 * t * t)
        return Maths.addArrays(Maths.addArrays(pA, pB), pC)

    @staticmethod
    def qprimeprime(ctrlPoly, t):
        return Maths.addArrays(
            Maths.mulItems(
                Maths.addArrays(
                    Maths.subtract(ctrlPoly[2], Maths.mulItems(ctrlPoly[1], 2)),
                    ctrlPoly[0],
                ),
                6 * (1.0 - t),
            ),
            Maths.mulItems(
                Maths.addArrays(
                    Maths.subtract(ctrlPoly[3], Maths.mulItems(ctrlPoly[2], 2)),
                    ctrlPoly[1],
                ),
                6 * t,
            ),
        )


def fitCurve(points, maxError, progressCallback=None):
    if not isinstance(points, list):
        raise TypeError("First argument should be an array")
    for point in points:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or not isinstance(point[0], (int, float))
            or not isinstance(point[1], (int, float))
        ):
            raise ValueError("Each point should be an array of two numbers")
    # Remove duplicate points
    points = [
        points[i]
        for i in range(len(points))
        if i == 0
        or (points[i][0] != points[i - 1][0] or points[i][1] != points[i - 1][1])
    ]

    if len(points) < 2:
        return []

    leftTangent = createTangent(points[1], points[0])
    rightTangent = createTangent(points[-2], points[-1])

    return fitCubic(points, leftTangent, rightTangent, maxError, progressCallback)


def fitCubic(points, leftTangent, rightTangent, error, progressCallback=None):
    MaxIterations = 20

    # Use heuristic if region only has two points in it
    if len(points) == 2:
        dist = Maths.vectorLen(Maths.subtract(points[0], points[1])) / 3.0
        bezCurve = [
            points[0],
            Maths.addArrays(points[0], Maths.mulItems(leftTangent, dist)),
            Maths.addArrays(points[1], Maths.mulItems(rightTangent, dist)),
            points[1],
        ]
        return [bezCurve]

    # Parameterize points, and attempt to fit curve
    u = chordLengthParameterize(points)
    bezCurve, maxError, splitPoint = generateAndReport(
        points, u, u, leftTangent, rightTangent, progressCallback
    )

    if maxError < error:
        return [bezCurve]

    # If error not too large, try some reparameterization and iteration
    if maxError < error * error:
        uPrime = u
        prevErr = maxError
        prevSplit = splitPoint

        for i in range(MaxIterations):
            uPrime = reparameterize(bezCurve, points, uPrime)
            bezCurve, maxError, splitPoint = generateAndReport(
                points, u, uPrime, leftTangent, rightTangent, progressCallback
            )

            if maxError < error:
                return [bezCurve]
            elif splitPoint == prevSplit:
                errChange = maxError / prevErr
                if 0.9999 < errChange < 1.0001:
                    break

            prevErr = maxError
            prevSplit = splitPoint

    # Fitting failed -- split at max error point and fit recursively
    beziers = []

    # To create a smooth transition from one curve segment to the next,
    # we calculate the tangent of the points directly before and after the center,
    # and use that same tangent both to and from the center point.
    centerVector = Maths.subtract(points[splitPoint - 1], points[splitPoint + 1])

    # However, should those two points be equal, the normal tangent calculation will fail.
    # Instead, we calculate the tangent from that "double-point" to the center point, and rotate 90deg.
    if centerVector[0] == 0 and centerVector[1] == 0:
        centerVector = Maths.subtract(points[splitPoint - 1], points[splitPoint])[::-1]
        centerVector[0] = -centerVector[0]

    toCenterTangent = Maths.normalize(centerVector)
    fromCenterTangent = Maths.mulItems(toCenterTangent, -1)

    beziers.extend(
        fitCubic(
            points[: splitPoint + 1],
            leftTangent,
            toCenterTangent,
            error,
            progressCallback,
        )
    )
    beziers.extend(
        fitCubic(
            points[splitPoint:],
            fromCenterTangent,
            rightTangent,
            error,
            progressCallback,
        )
    )
    return beziers


def generateAndReport(
    points, paramsOrig, paramsPrime, leftTangent, rightTangent, progressCallback=None
):
    bezCurve = generateBezier(points, paramsPrime, leftTangent, rightTangent)

    # Find max deviation of points to fitted curve.
    maxError, splitPoint = computeMaxError(points, bezCurve, paramsOrig)

    if progressCallback:
        progressCallback(
            {
                "bez": bezCurve,
                "points": points,
                "params": paramsOrig,
                "maxErr": maxError,
                "maxPoint": splitPoint,
            }
        )

    return bezCurve, maxError, splitPoint


def generateBezier(points, parameters, leftTangent, rightTangent):
    firstPoint = points[0]
    lastPoint = points[-1]
    bezCurve = [firstPoint, None, None, lastPoint]

    # Compute the A's
    A = Maths.zeros_Xx2x2(len(parameters))
    for i, u in enumerate(parameters):
        ux = 1 - u
        a = A[i]
        a[0] = Maths.mulItems(leftTangent, 3 * u * (ux * ux))
        a[1] = Maths.mulItems(rightTangent, 3 * ux * (u * u))

    # Create the C and X matrices
    C = [[0, 0], [0, 0]]
    X = [0, 0]
    for i, u in enumerate(parameters):
        a = A[i]

        C[0][0] += Maths.dot(a[0], a[0])
        C[0][1] += Maths.dot(a[0], a[1])
        C[1][0] += Maths.dot(a[0], a[1])
        C[1][1] += Maths.dot(a[1], a[1])

        tmp = Maths.subtract(
            points[i], Bezier.q([firstPoint, firstPoint, lastPoint, lastPoint], u)
        )

        X[0] += Maths.dot(a[0], tmp)
        X[1] += Maths.dot(a[1], tmp)

    # Compute the determinants of C and X
    det_C0_C1 = C[0][0] * C[1][1] - C[1][0] * C[0][1]
    det_C0_X = C[0][0] * X[1] - C[1][0] * X[0]
    det_X_C1 = X[0] * C[1][1] - X[1] * C[0][1]

    # Finally, derive alpha values
    alpha_l = 0 if det_C0_C1 == 0 else det_X_C1 / det_C0_C1
    alpha_r = 0 if det_C0_C1 == 0 else det_C0_X / det_C0_C1

    # If alpha negative, use the Wu/Barsky heuristic (see text).
    # If alpha is 0, you get coincident control points that lead to
    # divide by zero in any subsequent NewtonRaphsonRootFind() call.
    segLength = Maths.vectorLen(Maths.subtract(firstPoint, lastPoint))
    epsilon = 1.0e-6 * segLength
    if alpha_l < epsilon or alpha_r < epsilon:
        # Fall back on standard (probably inaccurate) formula, and subdivide further if needed.
        bezCurve[1] = Maths.addArrays(
            firstPoint, Maths.mulItems(leftTangent, segLength / 3.0)
        )
        bezCurve[2] = Maths.addArrays(
            lastPoint, Maths.mulItems(rightTangent, segLength / 3.0)
        )
    else:
        # First and last control points of the Bezier curve are
        # positioned exactly at the first and last data points
        # Control points 1 and 2 are positioned an alpha distance out
        # on the tangent vectors, left and right, respectively
        bezCurve[1] = Maths.addArrays(firstPoint, Maths.mulItems(leftTangent, alpha_l))
        bezCurve[2] = Maths.addArrays(lastPoint, Maths.mulItems(rightTangent, alpha_r))

    return bezCurve


def reparameterize(bezier, points, parameters):
    return [
        newtonRaphsonRootFind(bezier, point, u) for point, u in zip(points, parameters)
    ]


def newtonRaphsonRootFind(bez, point, u):
    """
    Use Newton-Raphson iteration to find better root.
    """
    d = Maths.subtract(Bezier.q(bez, u), point)
    qprime = Bezier.qprime(bez, u)
    numerator = Maths.mulMatrix(d, qprime)
    denominator = Maths.sum(
        Maths.addItems(
            Maths.squareItems(qprime), Maths.mulMatrix(d, Bezier.qprimeprime(bez, u))
        )
    )

    if denominator == 0:
        return u
    else:
        return u - numerator / denominator


def chordLengthParameterize(points):
    u = []
    currU = 0
    prevU = 0
    prevP = None
    for i, p in enumerate(points):
        if i:
            currU = prevU + Maths.vectorLen(Maths.subtract(p, prevP))
        u.append(currU)
        prevU = currU
        prevP = p

    prevU = u[-1]
    u = [x / prevU if prevU != 0 else 0.0 for x in u]
    return u


def computeMaxError(points, bez, parameters):
    maxDist = 0
    splitPoint = len(points) // 2
    t_distMap = mapTtoRelativeDistances(bez, 10)

    for i, point in enumerate(points):
        # Find 't' for a point on the bez curve that's as close to 'point' as possible:
        t = find_t(bez, parameters[i], t_distMap, 10)
        v = Maths.subtract(Bezier.q(bez, t), point)
        dist = v[0] * v[0] + v[1] * v[1]

        if dist > maxDist:
            maxDist = dist
            splitPoint = i

    return maxDist, splitPoint


def mapTtoRelativeDistances(bez, B_parts):
    B_t_dist = [0]
    B_t_prev = bez[0]
    sumLen = 0

    for i in range(1, B_parts + 1):
        B_t_curr = Bezier.q(bez, i / B_parts)
        sumLen += Maths.vectorLen(Maths.subtract(B_t_curr, B_t_prev))
        B_t_dist.append(sumLen)
        B_t_prev = B_t_curr

    # Normalize B_length to the same interval as the parameter distances; 0 to 1:
    if sumLen == 0:
        return [i / B_parts for i in range(B_parts + 1)]
    B_t_dist = [x / sumLen for x in B_t_dist]
    return B_t_dist


def find_t(bez, param, t_distMap, B_parts):
    if param < 0:
        return 0
    if param > 1:
        return 1

    t = 0.0
    for i in range(1, B_parts + 1):
        if param <= t_distMap[i]:
            tMin = (i - 1) / B_parts
            tMax = i / B_parts
            lenMin = t_distMap[i - 1]
            lenMax = t_distMap[i]
            if lenMax == lenMin:
                t = tMin
            else:
                t = (param - lenMin) / (lenMax - lenMin) * (tMax - tMin) + tMin
            break
    return t


def createTangent(pointA, pointB):
    return Maths.normalize(Maths.subtract(pointA, pointB))
