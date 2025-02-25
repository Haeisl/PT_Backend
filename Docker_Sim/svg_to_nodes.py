import logging
import math
from xml.dom import minidom

import numpy as np
from param import d_border, d_outerAct, d_rect
from svg.path import parse_path

logger = logging.getLogger("planningtool")


def rotate(origin, points, angle):
    """
    Rotate a set of 2D points around a given origin by a specified angle.

    Parameters
    ----------
    origin : tuple or list
        A tuple or list of length 2 (ox, oy), the rotation center.
    points : iterable
        An iterable of (x, y) coordinates to rotate.
    angle : float
        Rotation angle in radians.

    Returns
    -------
    numpy.ndarray
        A NumPy array of rotated points with shape (N, 2).
    """
    ox, oy = origin
    rotated_points = []
    for point in points:
        px = point[0]
        py = point[1]
        qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
        qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)

        rotated_point = np.array([qx,qy])
        rotated_point = np.expand_dims(rotated_point, axis=0)

        if rotated_points == []:
            rotated_points = rotated_point
        else:
            rotated_points = np.append(rotated_points, rotated_point, axis = 0)

    return rotated_points

def multiply_transforms(a, b):
    """
    Multiply two 2D transformation matrices in the format used by certain SVG attributes.

    Parameters
    ----------
    a : list or array
        The first transformation (6-element list or array).
    b : list or array
        The second transformation (6-element list or array).

    Returns
    -------
    list
        A list of 6 floats representing the combined transform a*b.
    """
    retval = [
        a[0]*b[0]+a[2]*b[1],  # 0
        a[1]*b[0]+a[3]*b[1],  # 1
        a[0]*b[2]+a[2]*b[3],  # 2
        a[1]*b[2]+a[3]*b[3],  # 3
        a[0]*b[4]+a[2]*b[5]+a[4],  # 4
        a[1]*b[4]+a[3]*b[5]+a[5]   # 5
        ]
    return retval

def get_point_at(path, distance, scale, offset):
    """
    Retrieve a point on an SVG path at a given normalized distance, applying scale and offset.

    Parameters
    ----------
    path : svg.path.Path
        A parsed SVG path object (from svg.path).
    distance : float
        A float in [0,1] indicating the fractional distance along the path.
    scale : float
        A float that scales the resulting x and y coordinates.
    offset : complex or tuple
        A complex number (or tuple converted to complex) to translate the point.

    Returns
    -------
    tuple
        A tuple (x, y) for the point at the specified location on the path.
    """
    pos = path.point(distance)
    pos += offset
    pos *= scale
    return pos.real, pos.imag


def points_from_path(path, density, scale, offset):
    """
    Generate points along an SVG path with a given density, scale, and offset.

    Parameters
    ----------
    path : svg.path.Path
        A parsed SVG path object.
    density : float
        A float controlling how many samples to take per unit length of the path.
    scale : float
        A float factor to scale each (x, y) coordinate.
    offset : complex or tuple
        A complex number or tuple that offsets each point.

    Returns
    -------
    generator
        A generator yielding (x, y) coordinate pairs sampled from the path.
    """
    step = int(path.length() * density)
    last_step = step - 1

    if last_step == 0:
        yield get_point_at(path, 0, scale, offset)
        return

    for distance in range(step):
        yield get_point_at(
            path, distance / last_step, scale, offset)


def points_from_doc(doc, density: float = 5, scale: float = 1, offset: tuple = (0,0)):
    """
    Extract points from all <path> elements in an SVG DOM document.

    Parameters
    ----------
    doc : xml.dom.minidom.Document
        A minidom parsed SVG document object.
    density : float, optional
        A float controlling sampling density along each path.
    scale : float, optional
        A float scale factor applied to each point.
    offset : tuple, optional
        A tuple (offset_x, offset_y) used for translation.

    Returns
    -------
    list
        A list of (x, y) floats representing sampled points from all paths.
    """
    offset = offset[0] + offset[1] * 1j
    points = []

    for element in doc.getElementsByTagName("path"):
        for path in parse_path(element.getAttribute("d")):
            points.extend(points_from_path(
                path, density, scale, offset))

    return points

def rescale_linear(array, new_min, new_max):
    """
    Rescale a 2D NumPy array to a new range [new_min, new_max] along each dimension.

    Parameters
    ----------
    array : numpy.ndarray
        A NumPy array of shape (N, 2), where the first column is x-coordinates
        and the second column is y-coordinates.
    new_min : float
        The new minimum value after rescaling.
    new_max : float
        The new maximum value after rescaling.

    Returns
    -------
    numpy.ndarray
        The modified array, also returned for convenience.
    """
    minimum_x, maximum_x = np.min(array[:,0]), np.max(array[:,0])
    m_x = (new_max - new_min) / (maximum_x - minimum_x)
    b_x = new_min - m_x * minimum_x
    array[:,0] = m_x * array[:,0] + b_x

    minimum_y, maximum_y = np.min(array[:,1]), np.max(array[:,1])
    m_y = (new_max - new_min) / (maximum_y - minimum_y)
    b_y = new_min - m_y * minimum_y
    array[:,1] = m_y * array[:,1] + b_y

    return array

def svg_to_nodes(svg_file: str, rotation_angle: float = 0) -> np.ndarray:
    """
    Convert an SVG file (containing one or more paths) into a NumPy array of 2D points.

    Parameters
    ----------
    svg_file : str
        Path to an SVG file that defines shape outlines via <path> elements.
    rotation_angle : float, optional
        The angle (in degrees) by which to rotate the resulting points about (0,0).

    Returns
    -------
    numpy.ndarray
        A NumPy array of shape (N, 2), containing the processed (x, y) points.
    """
    #svg_file = param.isolation_shape  # without dots inside isoalation, correct order of paths (from top-left corner, clockwise)

    doc = minidom.parse(svg_file)
    points = points_from_doc(doc, 0.5, 5, (0, 5))
    logger.info(f"Isolation vertices number = {len(points)}")

    # x and y are symmetric about zero
    points_np = np.round(np.array(points),2)
    points_np[:,0] -= (np.min(points_np[:,0]) + np.max(points_np[:,0]))/2
    points_np[:,1] -= (np.min(points_np[:,1]) + np.max(points_np[:,1]))/2

    new_max = d_rect/2 + d_outerAct/2 + d_border # 1/2 of the line between peripheral electrodes + peripheral electrodes radius + size of silicon pad after electrode border

    points_np = rescale_linear(points_np, -new_max, new_max)

    points_np[:,0] = np.round(points_np[:,0],2)
    points_np[:,1] = np.round(points_np[:,1],2)

    # rotate around 0 to check influence of the shape on the result
    points_np = np.array(rotate([0, 0], points_np, math.radians(rotation_angle)))

    points_np[:,0] = np.round(points_np[:,0],2)
    points_np[:,1] = np.round(points_np[:,1],2)

    doc.unlink()

    return points_np