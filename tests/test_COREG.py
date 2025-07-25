#!/usr/bin/env python
# -*- coding: utf-8 -*-

# AROSICS - Automated and Robust Open-Source Image Co-Registration Software
#
# Copyright (C) 2017-2024
# - Daniel Scheffler (GFZ Potsdam, daniel.scheffler@gfz.de)
# - GFZ Helmholtz Centre for Geosciences Potsdam,
#   Germany (https://www.gfz.de/)
#
# This software was developed within the context of the GeoMultiSens project funded
# by the German Federal Ministry of Education and Research
# (project grant code: 01 IS 14 010 A-C).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the global co-registration module of AROSICS."""

import unittest
import shutil
import os
import numpy as np
import warnings

# custom
from .cases import test_cases
import pytest
from arosics import COREG
from geoarray import GeoArray
from osgeo import gdal  # noqa
from py_tools_ds.geo.projection import EPSG2WKT


class COREG_GLOBAL_init(unittest.TestCase):
    """Test case on object initialization of COREG_LOCAL."""

    def setUp(self):
        self.ref_path = test_cases['INTER1']['ref_path']
        self.tgt_path = test_cases['INTER1']['tgt_path']
        self.coreg_kwargs = test_cases['INTER1']['kwargs_global']
        self.coreg_kwargs['wp'] = test_cases['INTER1']['wp_inside']

    def test_coreg_init_from_disk(self):
        self.CRL = COREG(self.ref_path, self.tgt_path, **self.coreg_kwargs)

    def test_coreg_init_from_inMem_GeoArray(self):
        # get GeoArray instances
        self.ref_gA = GeoArray(self.ref_path)
        self.tgt_gA = GeoArray(self.tgt_path)

        # assure the raster data are in-memory
        self.ref_gA.to_mem()
        self.tgt_gA.to_mem()

        # get instance of COREG_LOCAL object
        self.CRL = COREG(self.ref_gA, self.tgt_gA, **self.coreg_kwargs)

    def test_empty_image(self):
        # get GeoArray instances
        self.ref_gA = GeoArray(self.ref_path)
        self.tgt_gA = GeoArray(self.tgt_path)

        # assure the raster data are in-memory
        self.ref_gA.to_mem()
        self.tgt_gA.to_mem()

        # fill the reference image with nodata
        self.ref_gA[:] = self.ref_gA.nodata

        # get instance of COREG_LOCAL object
        with pytest.raises(RuntimeError, match='.*only contains nodata values.'):
            COREG(self.ref_gA, self.tgt_gA, **self.coreg_kwargs)

    def test_init_warnings(self):
        with pytest.warns(UserWarning, match='.*window size.*rather small value.*'):
            COREG(self.ref_path, self.tgt_path, **dict(ws=(63, 63), **self.coreg_kwargs))
        # TODO: test the other warnings


class CompleteWorkflow_INTER1_S2A_S2A(unittest.TestCase):
    """Test case for the complete workflow of global co-registration based on two Sentinel-2 datasets, one with
    ~25% cloud cover, the other one without any clouds. The subsets cover the S2A tiles only partly (nodata areas
    are present).
    """

    def setUp(self):
        self.ref_path = test_cases['INTER1']['ref_path']
        self.tgt_path = test_cases['INTER1']['tgt_path']
        self.coreg_kwargs = test_cases['INTER1']['kwargs_global']

    def tearDown(self):
        """Delete output."""
        dir_out = os.path.dirname(self.coreg_kwargs['path_out'])
        if os.path.isdir(dir_out):
            shutil.rmtree(dir_out)

    @staticmethod
    def run_shift_detection_correction(ref, tgt, **params):
        # get instance of COREG_LOCAL object
        CR = COREG(ref, tgt, **params)

        # calculate global X/Y shift
        CR.calculate_spatial_shifts()

        # test shift correction and output writer
        CR.correct_shifts()

        assert os.path.exists(params['path_out']), 'Output of global co-registration has not been written.'

        return CR

    def test_shift_calculation_with_default_params(self):
        """Test with default parameters - should compute X/Y shifts properly and write the de-shifted target image."""

        CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path,
                                                 **dict(self.coreg_kwargs,
                                                        footprint_poly_ref=None,
                                                        footprint_poly_tgt=None))
        assert CR.success

    def test_shift_calculation_with_image_coords_only(self):
        """Test with default parameters - should compute X/Y shifts properly and write the de-shifted target image."""
        # FIXME fails when executed alone

        # overwrite gt and prj
        ref = GeoArray(self.ref_path)
        ref.to_mem()
        ref.filePath = None
        ref.gt = [0, 1, 0, 0, 0, -1]
        ref.prj = ''
        tgt = GeoArray(self.tgt_path)
        tgt.to_mem()
        tgt.filePath = None
        tgt.gt = [0, 1, 0, 0, 0, -1]
        tgt.prj = ''

        CR = self.run_shift_detection_correction(ref, tgt,
                                                 **dict(self.coreg_kwargs,
                                                        wp=(1200, -1600),
                                                        footprint_poly_ref=None,
                                                        footprint_poly_tgt=None))
        assert CR.success

    def test_shift_calculation_with_float_coords(self):
        """Test with default parameters - should compute X/Y shifts properly and write the de-shifted target image."""

        # overwrite gt and prj
        ref = GeoArray(self.ref_path)
        ref.to_mem()
        ref.filePath = None
        ref.gt = [330000.00000001, 10.1, 0.0, 5862000.0000001, 0.0, -10.1]
        tgt = GeoArray(self.tgt_path)
        tgt.to_mem()
        tgt.filePath = None
        tgt.gt = [335440.0000001, 10.1, 0.0, 5866490.0000001, 0.0, -10.1]

        CR = self.run_shift_detection_correction(ref, tgt,
                                                 **dict(self.coreg_kwargs,
                                                        wp=(341500.0, 5861440.0),
                                                        footprint_poly_ref=None,
                                                        footprint_poly_tgt=None))
        assert CR.success

    def test_shift_calculation_nonquadratic_pixels(self):
        """Test with default parameters - should compute X/Y shifts properly and write the de-shifted target image."""

        # overwrite gt and prj
        ref = GeoArray(self.ref_path)
        ref.to_mem()
        ref.filePath = None
        ref.gt = [330000.00000001, 5.8932, 0.0, 5862000.0000001, 0.0, -10.1]
        tgt = GeoArray(self.tgt_path)
        tgt.to_mem()
        tgt.filePath = None
        tgt.gt = [335440.0000001, 5.8933, 0.0, 5866490.0000001, 0.0, -10.1]

        CR = self.run_shift_detection_correction(ref, tgt,
                                                 **dict(self.coreg_kwargs,
                                                        wp=(341500.0, 5861440.0),
                                                        footprint_poly_ref=None,
                                                        footprint_poly_tgt=None))
        assert CR.success

    def test_shift_calculation_with_metaRotation(self):
        """Test with default parameters - should compute X/Y shifts properly and write the de-shifted target image."""

        # overwrite gt and prj
        ref = GeoArray(self.ref_path)
        ref.to_mem()
        ref.filePath = None
        ref.gt = [330000, 10, 0.0, 5862000, 0.0, -10]
        tgt = GeoArray(self.tgt_path)
        tgt.to_mem()
        tgt.filePath = None
        # tgt.gt = [335440, 5.8932, 0.0, 5866490, 0.0, -10.1]
        tgt.gt = [335440, 10, 0.00001, 5866490, 0.00001, -10]

        with pytest.warns(UserWarning, match='.*target image needs to be resampled.*'):
            CR = self.run_shift_detection_correction(ref, tgt,
                                                     **dict(self.coreg_kwargs,
                                                            # ws=(512, 512),
                                                            wp=(341500.0, 5861440.0),
                                                            footprint_poly_ref=None,
                                                            footprint_poly_tgt=None,
                                                            max_shift=35))
        CR.show_matchWin(interactive=False, after_correction=None)
        assert CR.success

    def test_shift_calculation_with_mask(self):
        """Test COREG if bad data mask is given."""
        ref = GeoArray(self.ref_path)
        tgt = GeoArray(self.tgt_path)

        mask = np.zeros((tgt.rows, tgt.cols), dtype=bool)
        mask[1000:1100, 1000:1100] = True
        gA_mask = GeoArray(mask, tgt.gt, tgt.prj)

        CR = self.run_shift_detection_correction(ref, tgt,
                                                 **dict(self.coreg_kwargs,
                                                        mask_baddata_tgt=gA_mask))
        CR.show_matchWin(interactive=False, after_correction=None)
        assert CR.success

    def test_shift_calculation_inmem_gAs_path_out_auto(self):
        """Test input parameter path_out='auto' in case input reference/ target image are in-memory GeoArrays."""
        ref = GeoArray(np.random.randint(1, 100, (1000, 1000)))
        tgt = GeoArray(np.random.randint(1, 100, (1000, 1000)))

        with pytest.raises(ValueError):
            self.run_shift_detection_correction(ref, tgt,
                                                **dict(self.coreg_kwargs,
                                                       path_out='auto',
                                                       fmt_out='ENVI',
                                                       v=True))

    # @pytest.mark.skip
    def test_shift_calculation_verboseMode(self):
        """Test the verbose mode - runs the functions of the plotting submodule."""
        with warnings.catch_warnings():
            warnings.filterwarnings(
                'ignore', category=UserWarning, message='Matplotlib is currently using agg, '
                                                        'which is a non-GUI backend, so cannot show the figure.')
            CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path,
                                                     **dict(self.coreg_kwargs, v=True))
            assert CR.success

    def test_shift_calculation_windowCoveringNodata(self):
        """Test shift detection if the matching window (defined by 'wp' and 'ws') covers the nodata area.

        Detected subpixel shifts (X/Y): 0.280572488796/-0.11016529071
        Calculated map shifts (X,Y): -7.19427511207/-18.8983470928
        """
        # TODO compare to expected results

        CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path,
                                                 **dict(self.coreg_kwargs,
                                                        wp=test_cases['INTER1']['wp_covering_nodata'],
                                                        ws=(256, 256)))
        assert CR.success

    def test_shift_calculation_windowAtImageEdge(self):
        """Test shift detection if the matching window is close to an image edge without covering nodata pixels.

        Detected subpixel shifts (X/Y): 0.34361492307/-0.320197995758
        Calculated map shifts (X,Y): -6.56385076931/-16.7980200425
        """
        # TODO compare to expected results

        CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path,
                                                 **dict(self.coreg_kwargs,
                                                        wp=test_cases['INTER1']['wp_close_to_edge'], ws=(256, 256)))
        assert CR.success

    def test_shift_calculation_noWGS84(self):
        """Test if a RunTimeError is raised in case the input projection datum is not WGS84."""
        ref = GeoArray(self.ref_path).to_mem()
        tgt = GeoArray(self.tgt_path).to_mem()

        # force to overwrite projection
        ref.filePath = None
        tgt.filePath = None
        ref.prj = EPSG2WKT(3035)  # ETRS89_LAEA_Europe
        tgt.prj = EPSG2WKT(3035)  # ETRS89_LAEA_Europe

        CR = self.run_shift_detection_correction(ref, tgt, **dict(self.coreg_kwargs))
        assert CR.success

    def test_shift_calculation_different_geographic_datum(self):
        """Test if a RunTimeError is raised in case of a different geographic datum."""
        ref = GeoArray(self.ref_path).to_mem()
        tgt = GeoArray(self.tgt_path).to_mem()

        # force to overwrite projection
        ref.filePath = None
        ref.prj = EPSG2WKT(3035)  # ETRS89_LAEA_Europe

        with pytest.raises(RuntimeError):
            self.run_shift_detection_correction(ref, tgt, **dict(self.coreg_kwargs))

    def test_shift_calculation_windowOutside(self):
        """Test if shift computation raises a ValueError if the given window position is outside the image overlap."""
        with pytest.raises(ValueError):
            self.run_shift_detection_correction(self.ref_path, self.tgt_path,
                                                **dict(self.coreg_kwargs,
                                                       wp=test_cases['INTER1']['wp_outside']))

    def test_shift_calculation_windowAtClouds(self):
        """Test if shift computation raises a RunTimeError if the matching window is centered at a cloudy position."""
        with pytest.raises(RuntimeError):
            self.run_shift_detection_correction(self.ref_path, self.tgt_path,
                                                **dict(self.coreg_kwargs,
                                                       wp=test_cases['INTER1']['wp_cloudy'], ws=(256, 256)))

    def test_shift_calculation_differentInputGrids(self):
        """"""
        self.skipTest('Not yet implemented.')

    def test_shift_calculation_SSIMdecreases(self):
        """"""
        self.skipTest('Not yet implemented.')

    # @pytest.mark.skip
    def test_plotting_after_shift_calculation(self):  # , mock_show):
        """Test plotting functionality."""
        # mock_show.return_value = None  # probably not necessary here in your case
        CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path, **self.coreg_kwargs)
        assert CR.success

        # test all the visualization functions
        with warnings.catch_warnings():
            warnings.filterwarnings(
                'ignore', category=UserWarning, message='Matplotlib is currently using agg, '
                                                        'which is a non-GUI backend, so cannot show the figure.')
            CR.show_cross_power_spectrum()
            CR.show_matchWin(interactive=False, after_correction=None)
            CR.show_matchWin(interactive=False, after_correction=True)
            CR.show_matchWin(interactive=False, after_correction=False)
            try:
                # __IPYTHON__  # noqa
                CR.show_cross_power_spectrum(interactive=True)
                CR.show_matchWin(interactive=True, after_correction=None)  # only works if test is started with ipython
                CR.show_matchWin(interactive=True, after_correction=True)
                CR.show_matchWin(interactive=True, after_correction=False)
            except NameError:
                pass
            CR.show_image_footprints()

    def test_correct_shifts_without_resampling(self):
        kw = self.coreg_kwargs.copy()
        kw['align_grids'] = False  # =default
        kw['progress'] = True

        CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path, **kw)
        assert CR.success
        assert CR.deshift_results['is shifted']
        assert not CR.deshift_results['is resampled']
        assert np.array_equal(CR.shift[:], CR.deshift_results['arr_shifted'])
        assert not np.array_equal(np.array(CR.shift.gt), np.array(CR.deshift_results['updated geotransform']))

    def test_correct_shifts_with_resampling(self):
        kw = self.coreg_kwargs.copy()
        kw['align_grids'] = True
        kw['progress'] = True

        CR = self.run_shift_detection_correction(self.ref_path, self.tgt_path, **kw)
        assert CR.success
        assert CR.deshift_results['is shifted']
        assert CR.deshift_results['is resampled']
        assert not np.array_equal(CR.shift[:], CR.deshift_results['arr_shifted'])
        assert np.array_equal(np.array(CR.shift.gt), np.array(CR.deshift_results['updated geotransform']))

    def test_correct_shifts_gdal_creation_options(self):
        """Test if the out_crea_options parameter works."""
        kw = self.coreg_kwargs.copy()
        kw['fmt_out'] = "GTiff"
        kw['out_crea_options'] = ["COMPRESS=DEFLATE", "BIGTIFF=YES", "ZLEVEL=9", "BLOCKXSIZE=512", "BLOCKYSIZE=512"]

        # in case the output data is not resampled
        self.run_shift_detection_correction(self.ref_path, self.tgt_path, **kw)
        assert 'COMPRESSION=DEFLATE' in gdal.Info(kw['path_out'])

        # in case the output data is resampled
        kw['align_grids'] = True
        self.run_shift_detection_correction(self.ref_path, self.tgt_path, **kw)
        assert 'COMPRESSION=DEFLATE' in gdal.Info(kw['path_out'])


if __name__ == '__main__':
    pytest.main()
