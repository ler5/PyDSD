# -*- coding: utf-8 -*-
import numpy as np
import pytmatrix
from pytmatrix.tmatrix import Scatterer
from pytmatrix.psd import PSDIntegrator
from pytmatrix import orientation, radar, tmatrix_aux, refractive
import DSR
from expfit import expfit
from scipy.optimize import curve_fit


class DropSizeDistribution(object):

    '''
    DropSizeDistribution class to hold DSD's and calculate parameters
    and relationships. Should be returned from the disdrometer*reader
    functions.
    '''

    def __init__(self, time, Nd, spread, rain_rate=None, velocity=None, Z=None,
                 num_particles=None, bin_edges=None, diameter=None):
        self.time = time
        self.Nd = Nd
        self.spread = spread
        self.rain_rate = rain_rate
        self.velocity = velocity
        self.Z = Z
        self.num_particles = num_particles
        self.bin_edges = bin_edges
        self.diameter = diameter

        lt = len(time)
        self.Zh = np.zeros(lt)
        self.Zdr = np.zeros(lt)
        self.Kdp = np.zeros(lt)
        self.Ai = np.zeros(lt)

    def calc_radar_parameters(self, wavelength=tmatrix_aux.wl_X):
        '''
        Calculates the radar parameters and stores them in the object.
        Defaults to X-Band,Beard and Chuang 10C setup.

        Sets object radar parameters:
            Zh, Zdr, Kdp, Ai

        Parameter:
            wavelength = pytmatrix supported wavelength.
        '''
        self._setup_scattering(wavelength)

        for t in range(0, len(self.time)):
            BinnedDSD = pytmatrix.psd.BinnedPSD(self.bin_edges,  self.Nd[t])
            self.scatterer.psd = BinnedDSD
            self.scatterer.set_geometry(tmatrix_aux.geom_horiz_back)
            self.Zdr[t] = 10 * np.log10(radar.Zdr(self.scatterer))
            self.Zh[t] = 10 * np.log10(radar.refl(self.scatterer))
            self.scatterer.set_geometry(tmatrix_aux.geom_horiz_forw)
            self.Kdp[t] = radar.Kdp(self.scatterer)
            self.Ai[t] = radar.Ai(self.scatterer)

    def _setup_scattering(self, wavelength):
        '''
        This internal function sets up the scattering table. It takes the
        wavelength as an argument where wavelength is one of the pytmatrix
        accepted wavelengths.
        '''
        self.scatterer = Scatterer(wavelength=wavelength,
                                   m=refractive.m_w_10C[wavelength])
        self.scatterer.psd_integrator = PSDIntegrator()
        self.scatterer.psd_integrator.axis_ratio_func = lambda D: 1.0 / \
            DSR.bc(D)
        self.scatterer.psd_integrator.D_max = 10.0
        self.scatterer.psd_integrator.geometries = (
            tmatrix_aux.geom_horiz_back, tmatrix_aux.geom_horiz_forw)
        self.scatterer.or_pdf = orientation.gaussian_pdf(20.0)
        self.scatterer.orient = orientation.orient_averaged_fixed
        self.scatterer.psd_integrator.init_scatter_table(self.scatterer)

    def _calc_mth_moment(self, m):
        '''
        Calculates the mth moment of the drop size distribution.
        '''

        bin_width = [self.bin_edges[i + 1] - self.bin_edges[i]
                     for i in range(0, len(self.bin_edges) - 1)]
        mth_moment = np.zeros(len(np.time))

        for t in range(0, len(self.time)):
            dmth = np.power(self.diameter, m)
            mth_moment[t] = np.multiply(np.multiply(dmth, self.Nd), bin_width)

        return mth_moment

#    def _calc_dsd_parameterization(self):
#        '''
#        This calculates the dsd parameterization. This includes the following
#        parameters:
#        Nt, W, D0, Nw
#
#        For D0 and Nw we use the method due to Bringi and Chandrasekar.
#
#        '''
#
#        self.Nt = np.zeros(len(self.time))
#        self.W = np.zeros(len(self.time))
#        self.D0 = np.zeros(len(self.time))
#        self.Nw = np.zeros(len(self.time))
#        self.Dmax = np.zeros(len(self.time))
#
# rho_w = 1  # Density of Water
#        vol_constant = 10e-03 * np.pi/6.0 * rho_w *n
#       for t in range(0,len(self.time)):
#           self.Nt[t] = np.dot(self.spread,self.Nd[t])
#           self.W[t] = vol_constant * np.dot(np.multiply(self.Nd[t],self.spread ),
#               array(self.diameter)**3)
#           self.D0[t] = self._calculate_D0(self.Nd[t])
# self.Nw[t]=   (3.67**4)/pi * (10**3 * self.W[t])/(self.D0[t]**4) #?
#           self.Dmax[t] =self.diameter[self.__get_last_nonzero(self.Nd[t])]

    def __get_last_nonzero(self, N):
        return np.max(N.nonzero())

#   def calculate_D0(self, N):
#       rho_w = 1

#       cum_W = 10**-3 * np.pi /6 * rho_w * \
#               np.cumsum([N[k]*self.spread[k]*(self.diameter[k]**3) for k in range(0,len(N))])
#       cross_pt = list(cum_W<(cum_W[-1]*0.5)).index(False)-1
#       slope = (cum_W[cross_pt+1]-cum_W[cross_pt])/(self.diameter[cross_pt+1]-self.diameter[cross_pt])
#       run = (0.5*cum_W[-1]-cum_W[cross_pt])/slope
#       return self.diameter[cross_pt]+run

    def calculate_RR(self):
        self.rain_rate = np.zeros(len(self.time))
        for t in range(0, len(self.time)):
            # self.rain_rate[t] = 0.6*3.1415 * 10**(-3) * np.dot(np.multiply(self.velocity,np.multiply(self.Nd[t],self.spread )),
            #    np.array(self.diameter)**3)
            velocity = 9.65 - 10.3 * np.exp(-0.6 * self.diameter)
            velocity[0] = 0.5
            self.rain_rate[t] = 0.6 * np.pi * 1e-03 * np.sum(self.mmultiply(
                velocity, self.Nd[t], self.spread, np.array(self.diameter) ** 3))

    def calc_R_kdp_relationship(self):
        '''
        calc_R_kdp_relationship calculates a power fit for the rainfall-kdp
        relationship based upon the calculated radar parameters(which should
        have already been run). It returns the scale and exponential
        parameter a and b in the first tuple, and the second returned argument
        gives the covariance matrix of the fit.
        '''

        filt = np.logical_and(self.Kdp > 0, self.rain_rate > 0)
        popt, pcov = expfit(self.Kdp[filt],
                            self.rain_rate[filt])

        return popt, pcov

    def calc_R_Zh_relationship(self):
        '''
        calc_R_Zh_relationship calculates the power law fit for Zh based
        upon scattered radar parameters. It returns the scale and exponential
        parameter a and b in the first tuple, and the second returned argument
        gives the covariance matrix of the fit.
        '''

        popt, pcov = expfit(np.power(10, 0.1 * self.Zh[self.rain_rate > 0]),
                            self.rain_rate[self.rain_rate > 0])
        return popt, pcov

    def calc_rainfall_relationship(self, moments):
        '''
        Calculate the rainfall empirical relationship. Moments is a
        list of which parameters you want the relationship for. This uses
        whatever frequency/temp the radar data was simulated at.
        Current options are:
        ['reflectivity' , 'differential_reflectivity' , 'specific_differential_phase']

        Usage:
        popt, pcov = calc_R_relationship(['reflectivity', 'differential_reflectivity'])

        Returns:
        Optimal parameters, covariance of fit
        '''
        if self.rain_rate is None:
            print('No Rain Rate Present')
            return None
        if self.Zh is None:
            print('No Radar Calculated Variables Present. \
                    Please run calc_radar_moments()')
            return None
        if moments is None:
            print('No moments selected')
            return None

        filt = np.logical_and(self.Kdp > 0, self.rain_rate > 0)
        # I'm having a stupid day and couldn't figure
        # out a more elegant way of doing this.
        lzh = len(self.Zh)
        x1 = np.ones(lzh)
        x2 = np.ones(lzh)
        x3 = np.ones(lzh)

        if 'reflectivity' in moments:
            x1 = self.Zh
        if 'differential_reflectivity' in moments:
            x2 = self.Zdr
        if 'specific_differential_phase' in moments:
            x3 = self.Kdp

        if len(moments) == 3:
            fit_func = lambda x1, x2, x3, a, b, c, d: a * \
               np.multiply(np.multiply( np.power(self.__idb(x1), b), np.power(self.__idb(x2),c)), np.power(x3,d))
            popt, pcov = curve_fit(fit_func, (x1[filt], x2[filt], x3[filt]),
                    (1, 1, 1, 1))
            return popt, pcov
        if len(moments) < 3:
            print('Have not implemented 2 yet')

        return None

    def __idb(self, db):
        return np.power(10, np.multiply(0.1, db))

    def mmultiply(self, *args):
        i_value = np.ones(len(args[0]))
        for i in args:
            i_value = np.multiply(i_value, i)

        return i_value
