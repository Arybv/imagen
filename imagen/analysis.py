"""
The ImaGen analysis module provides common analysis functions, which
can be applied to any SheetView or SheetStack. This allows the user to
perform analyses on their input patterns or any other arrays embedded
within a SheetView and display the output of the analysis alongside
the original patterns.

Currently this module provides FFT, auto-correlation and gradient
analyses as well the analysis baseclass, which will apply any
TransferFn to the data.
"""

import numpy as np
from numpy.fft.fftpack import fft2
from numpy.fft.helper import fftshift

import param
from param import ParamOverrides

from dataviews import SheetView, SheetStack,  SheetLayer
from dataviews.sheetcoords import BoundingBox

from imagen import wrap
from transferfn import TransferFn



class SheetOperation(param.ParameterizedFunction):
    """
    A SheetOperation is a transformation that operates on the
    SheetLayer level.
    """

    def _process(self, view,p=None):
        """
        A single SheetLayer may be returned but multiple SheetLayer
        outputs may be returned as a tuple..
        """
        raise NotImplementedError

    def __call__(self, view, **params):
        self.p = ParamOverrides(self, params)

        if isinstance(view, SheetLayer):
            return self._process(view, self.p)
        elif isinstance(view, SheetStack):
            return view.map(self._process)
        else:
            raise TypeError("Not a SheetLayer or SheetStack.")



class analysis(SheetOperation):
    """
    The analysis baseclass provides support for processing
    SheetStacks, SheetViews and lists of SheetView objects. The actual
    transformation is performed by the _process method, which can be
    subclassed to provide any desired transformation, however by
    default it will apply the supplied transfer_fn.
    """

    transfer_fns = param.List(default=[], class_=TransferFn)

    def _process(self, sheetview):
        data = sheetview.data.copy()
        for transfer_fn in self.p.transfer_fns:
            data = transfer_fn(data)
        return SheetView(data, sheetview.bounds, metadata=sheetview.metadata)



class fft_power_spectrum(SheetOperation):
    """
    Compute the 2D Fast Fourier Transform (FFT) of the supplied sheet view.

    Example::
    fft_power_spectrum(topo.sim.V1.views.maps.OrientationPreference)
    """

    peak_val = param.Number(default=1.0)

    def _process(self, sheetview, p=None):
        cr = sheetview.cyclic_range
        data = sheetview.data if cr is None else sheetview.data/cr
        fft_spectrum = abs(fftshift(fft2(data - 0.5, s=None, axes=(-2, -1))))
        fft_spectrum = 1 - fft_spectrum # Inverted spectrum by convention
        zero_min_spectrum = fft_spectrum - fft_spectrum.min()
        spectrum_range = fft_spectrum.max() - fft_spectrum.min()
        normalized_spectrum = (self.p.peak_val * zero_min_spectrum) / spectrum_range

        l, b, r, t = sheetview.bounds.lbrt()
        density = sheetview.xdensity
        bb = BoundingBox(radius=(density/2)/(r-l))

        return SheetView(normalized_spectrum, bb, metadata=sheetview.metadata)



class gradient(SheetOperation):
    """
    Compute the gradient plot of the supplied SheetView or SheetStack.
    Translated from Octave code originally written by Yoonsuck Choe.

    If the SheetView has a cyclic_range, negative differences will be
    wrapped into the range.

    Example:: gradient(topo.sim.V1.views.maps.OrientationPreference)
    """

    def _process(self, sheetview):
        data = sheetview.data
        r, c = data.shape
        dx = np.diff(data, 1, axis=1)[0:r-1, 0:c-1]
        dy = np.diff(data, 1, axis=0)[0:r-1, 0:c-1]

        cyclic_range = 1.0 if sheetview.cyclic_range is None else sheetview.cyclic_range
        if cyclic_range is not None: # Wrap into the specified range
            # Convert negative differences to an equivalent positive value
            dx = wrap(0, cyclic_range, dx)
            dy = wrap(0, cyclic_range, dy)
            #
            # Make it increase as gradient reaches the halfway point,
            # and decrease from there
            dx = 0.5 * cyclic_range - np.abs(dx - 0.5 * cyclic_range)
            dy = 0.5 * cyclic_range - np.abs(dy - 0.5 * cyclic_range)

        return SheetView(np.sqrt(dx*dx + dy*dy), sheetview.bounds,
                         metadata=sheetview.metadata)



class autocorrelation(SheetOperation):
    """
    Compute the 2D autocorrelation of the supplied data. Requires the
    external SciPy package.

    Example::
    autocorrelation(topo.sim.V1.views.maps.OrientationPreference)
    """

    def _process(self, sheetview):
        import scipy.signal
        data = sheetview.data
        autocorr_data = scipy.signal.correlate2d(data, data)
        return SheetView(autocorr_data, sheetview.bounds,
                         metadata=sheetview.metadata)
