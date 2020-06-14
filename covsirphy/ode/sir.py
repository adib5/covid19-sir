#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
from covsirphy.ode.mbase import ModelBase


class SIR(ModelBase):
    """
    SIR model.
    """
    # Model name
    NAME = "SIR"
    # names of parameters
    PARAMETERS = ["rho", "sigma"]
    DAY_PARAMETERS = ["1/beta [day]", "1/gamma [day]"]
    # Variable names in dimensional ODEs
    VARIABLES = [super().S, super().SI, super().FR]
    # Priorities of the variables when optimization
    PRIORITIES = np.array([1, 1, 1])
    # Variables that increases monotonically
    VARS_INCLEASE = [super().FR]

    def __init__(self, population, rho, sigma):
        """
        @population <int>: total population
        parameter values of non-dimensional ODE model
            - @rho <float>
            - @sigma <float>
        """
        # Total population
        if not isinstance(population, int):
            raise TypeError("@population must be an integer.")
        self.population = population
        # Non-dim parameters
        self.rho = rho
        self.sigma = sigma

    def __call__(self, t, X):
        """
        Return the list of dS/dt (tau-free) etc.
        @return <np.array>
        """
        n, s, i, *_ = self.population, X
        dsdt = 0 - round(self.beta * s * i / n)
        drdt = round(self.sigma * i)
        didt = 0 - dsdt - drdt
        return np.array([dsdt, didt, drdt])

    @classmethod
    def param_range(cls, taufree_df, population):
        """
        Define the range of parameters (not including tau value).
        @taufree_df <pd.DataFrame>:
            - index: reset index
            - t <int>: time steps (tau-free)
            - columns with dimensional variables
        @population <int>: total population
        @return <dict[name]=(min, max)>:
            - min <float>: min value
            - max <float>: max value
        """
        df = cls.validate_dataframe(
            taufree_df, name="taufree_df", columns=[cls.TS, *cls.VARIABLES]
        )
        n, t, s, i, r = population, df[cls.TS], df[cls.S], df[cls.CI], df[cls.FR]
        # rho = - n * (dS/dt) / S / I
        rho_series = 0 - n * s.diff() / t.diff() / s / i
        # sigma = (dR/dt) / I
        sigma_series = r.diff() / t / i
        # Calculate quantile
        _dict = {
            k: v.quantile(cls.QUANTILE_RANGE)
            for (k, v) in zip(["rho", "sigma"], [rho_series, sigma_series])
        }
        return _dict

    @classmethod
    def specialize(cls, data_df, population):
        """
        Specialize the dataset for this model.
        @data_df <pd.DataFrame>:
            - index: reset index
            - Confirmed <int>: the number of confirmed cases
            - Infected <int>: the number of currently infected cases
            - Fatal <int>: the number of fatal cases
            - Recovered <int>: the number of recovered cases
            - any columns
        @population <int>: total population in the place
        @return <pd.DataFrame>:
            - index: reset index
            - any columns @data_df has
            - Susceptible <int>: the number of susceptible cases
            - Fatal or Recovered <int>: total number of fatal/recovered cases
        """
        df = super().specialize(data_df, population)
        # Calculate dimensional variables
        df[cls.S] = population - df[cls.C]
        df[cls.FR] = df[cls.F] + df[cls.R]
        return df

    def calc_r0(self):
        """
        Calculate (basic) reproduction number.
        """
        rt = self.rho / self.sigma
        return round(rt, 2)

    def calc_days_dict(self, tau):
        """
        Calculate 1/beta [day] etc.
        @param tau <int>: tau value [min]
        """
        _dict = {
            "1/beta [day]": int(tau / 24 / 60 / self.rho),
            "1/gamma [day]": int(tau / 24 / 60 / self.sigma)
        }
        return _dict
