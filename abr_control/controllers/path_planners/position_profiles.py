"""
A function defining the shape of our path from start to target
Restrictions
------------
- the path must start at [0, 0, 0] and end at [1, 1, 1]
    these are the start and target position, respectively
    The reason for this is that we just need to define the shape of
    our path with respect to the straight line path from start to
    target. The path planner will do the stretching so that the path
    at t==0 will be the start, and will end at the target
"""
import numpy as np
from abr_control.utils import colors as c
class PosProf():
    def __init__(self, tol=1e-6, n_sample_points=1000, **kwargs):
        """
        Must take n_sample_points as an argument. This defines how many samples
        are required to properly follow the shape of the path curve.
        """
        self.n_sample_points = n_sample_points
        endc = '\033[0m'
        assert sum(abs(self.step(0))) <= tol, (
            f"\n{c.red}Position profile must equal [0, 0, 0] at t=0\n" +
            f"step(0) function returning {self.step(0)}{endc}")
        step1 = self.step(1)
        for step in step1:
            assert abs(step-1) <= tol, (
                f"\n{c.red}Position profile must equal [1, 1, 1] at t=1\n" +
                f"step(1) function returning {self.step(1)}{endc}")

    def step(self, t):
        """
        Takes in a time from 0 to 1, and returns a 3x1 float array of positions.
        The output at t==0 must be [0, 0, 0] (within tol)
        The output at t==1 must be [1, 1, 1] (within tol)
        """
        raise NotImplementedError


class Linear(PosProf):
    def __init__(self, n_sample_points=1000, **kwargs):
        """
        Position profile that follows a linear path.

        Parameters
        ----------
        n_sample_points: int, Optional (Default: 1000)
            the number of points recommended to properly sample to curve function
        """
        super().__init__(n_sample_points=n_sample_points, **kwargs)

    def step(self, t):
        """
        Returns a 3x1 float array of positions that follow a linear ramp from
        [0, 0, 0] to [1, 1, 1] in the time range of 0 to 1.

        Parameters
        ----------
        t: float
            the time in the range of [0, 1]
        """
        return np.array([t, t, t])


class SinCurve(PosProf):
    def __init__(self, axes=None, cycles=None, n_sample_points=1000, **kwargs):
        """
        Position profile that follows a sin curve. Can specify which x, y, z,
        or combination of, should be curved with the `axes` parameter. Indices
        not included in here will have a straight line path. By default, the curve
        follows sin from 0 to pi/2 so that we end at [1, 1, 1]. We can also shorten
        the period so that we move multiples of 2pi - 3pi/2 with the cycles
        parameter.

        Parameters
        ----------
        axes: list of strings, Optional (Default: ['x'])
            Contains any combination of, 'x', 'y', or 'z'. These
            specify which dimensions will be warped by the sin curve. The indicies
            that are omitted from the list will have a straight path.
        cycles: list of ints, Optional (Default [1, 1, 1])
            Specifies the number of cycles of the sin curve to have. These are
            shifted cycles so that our curve always ends at [1, 1, 1]. When the
            value is 1 the curve goes from sin 0 to pi/2. When the value is 2 the
            curve goes from 0 to 5pi/2, etc.
        n_sample_points: int, Optional (Default: 1000)
            The number of points to use to interpolate the position curve. Increase
            for higher frequency paths
        """

        if axes is None:
            axes = ['x']
        if cycles is None:
            cycles = [1, 1, 1]
        self.axes = axes
        self.cycles = cycles
        # let user pass cycles as int, this adjust the period scaling accordingly
        for cc, cycle in enumerate(self.cycles):
            self.cycles[cc] = (self.cycles[cc]-1)*4 + 1
        super().__init__(n_sample_points=n_sample_points, **kwargs)

    def step(self, t):
        """
        Returns a linear path from [0, 0, 0] to [1, 1, 1], with the axes
        specified in the `axes` parameter being warped to follow a sin curve
        from 0Pi to ((cycles[index]-1)*4 + 1)Pi

        Parameters
        ----------
        t: float
            the time in the range of [0, 1]
        """
        if 'x' in self.axes:
            x = np.sin(self.cycles[0] * t*np.pi/2)
        else:
            x =t

        if 'y' in self.axes:
            y = np.sin(self.cycles[1] * t*np.pi/2)
        else:
            y =t

        if 'z' in self.axes:
            z = np.sin(self.cycles[2] * t*np.pi/2)
        else:
            z =t

        return np.array([x, y, z])


class FromPoints(PosProf):
    def __init__(self, pts, n_sample_points=1000, **kwargs):
        """
        Position profile generated from a list of points.

        Parameters
        ----------
        pts: 3xN array of floats
            The cartesian points of the path we will generate a function
            for. The value at t==0 must be [0, 0, 0] and t==1 at [1, 1, 1].
        n_sample_points: int, Optional (Default: 1000)
            the number of points recommended to properly sample to curve function
        """
        # interpolate into function
        if pts.shape[0] != 3:
            pts = pts.T
        x = np.linspace(0, 1, n_sample_points)

        self.X = scipy.interpolate.interp1d(x, pts[0])
        self.Y = scipy.interpolate.interp1d(x, pts[1])
        self.Z = scipy.interpolate.interp1d(x, pts[2])

        super().__init__(n_sample_points=n_sample_points, **kwargs)

    def step(self, t):
        """
        Returns the interpolated values at t

        Parameters
        ----------
        t: float
            the time in the range of [0, 1]
        """

        if t == 0:
            return np.zeros(3)
        if t == 1:
            return np.ones(3)

        xyz = np.array([self.X(t), self.Y(t), self.Z(t)])
        return xyz


class Ellipse(PosProf):
    def __init__(self, horz_stretch, plane='xy', n_sample_points=1000, **kwargs):
        """
        Position profile that follows an ellipse

        Parameters
        ----------
        horz_stretch: float
            the gain used to stretch the path horizontally (perpendicular to the
            direction of start to target). If horizontal stretch is negative, it
            will shift the curve to the opposite side
        plane: string of 2 char, Optional (Default: xy)
            Specifies which cartesian plane the ellipse should fall on
        n_sample_points: int, Optional (Default: 1000)
            the number of points recommended to properly sample to curve function
        """
        self.indices = {'x':0, 'y':1, 'z':2}
        self.plane = plane
        for key in self.indices:
            if key not in self.plane:
                self.linear_index = self.indices[key]

        # We generate the curve on the x axis, then rotate it to [1, 1, 1]
        self.b = horz_stretch
        # Rotate about z by 45
        G = -np.pi/4
        self.R = np.array([
            [np.cos(G), -np.sin(G)],
            [np.sin(G), np.cos(G)]]
        )
        # magnitude to stretch our rotated curve to [1, 1]
        self.mag = 2*np.sin(-G)

        super().__init__(n_sample_points=n_sample_points, **kwargs)

    def step(self, t):
        """
        Returns a curved path from [0, 0, 0] to [1, 1, 1] that follows an
        ellipse, with its horizontal stretching defined by horz_stretch on
        init.

        Parameters
        ----------
        t: float
            the time in the range of [0, 1]
        """

        # x = t in this case because we will rotate xy to [1, 1]
        # equation of ellipse solving for y, with the ellipse
        # centered at [0.5, 0], a=0.5, and b defined by the user
        y = self.b * np.sqrt(1 - (t-0.5)**2/0.5**2)
        xy = np.dot(np.array([t, y]), self.R) * self.mag
        out = np.zeros(3)
        out[self.indices[self.plane[0]]] = xy[0]
        out[self.indices[self.plane[1]]] = xy[1]
        out[self.linear_index] = t
        return out
