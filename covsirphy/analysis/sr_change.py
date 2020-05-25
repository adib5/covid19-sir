#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import numpy as np
import optuna
import pandas as pd
from covsirphy.cleaning.word import Word
from covsirphy.phase.trend import Trend
from covsirphy.phase.sr_data import SRData


class ChangeFinder(Word):
    """
    Find change points of S-R trend.
    """
    optuna.logging.disable_default_handler()

    def __init__(self, clean_df, population, country, province=None,
                 popualtion_change_dict=None):
        """
        @clean_df <pd.DataFrame>: cleaned data
            - index <int>: reseted index
            - Date <pd.TimeStamp>: Observation date
            - Country <str>: country/region name
            - Province <str>: province/prefecture/sstate name
            - Confirmed <int>: the number of confirmed cases
            - Infected <int>: the number of currently infected cases
            - Fatal <int>: the number of fatal cases
            - Recovered <int>: the number of recovered cases
        @population <int/dict>: initial value of total population in the place
        @country <str>: country name
        @province <str>: province name
        @popualtion_change_dict <dict[str]=int/None>:
            - dictionary of total population
                - key: start date of population change
                - value: total population
        """
        # Arguments
        self.clean_df = clean_df.copy()
        self.country = country
        self.province = province
        if province is None:
            self.name = country
        else:
            self.name = f"{country}{self.SEP}{province}"
        self.dates = self.get_dates(clean_df, population, country, province)
        self.pop_dict = self._read_population_data(
            self.dates, population, popualtion_change_dict
        )
        # Setting for optimization
        self.n_points = 0
        self.min_duration = 0
        self.change_dates = list()
        self.change_dates_previous = list()
        self.study = None
        self.run_time = 0
        self.total_trials = 0

    def get_dates(self, clean_df, population, country, province):
        """
        Get dates from the dataset.
        @clean_df <pd.DataFrame>: cleaned data
            - index <int>: reseted index
            - Date <pd.TimeStamp>: Observation date
            - Country <str>: country/region name
            - Province <str>: province/prefecture/sstate name
            - Confirmed <int>: the number of confirmed cases
            - Infected <int>: the number of currently infected cases
            - Fatal <int>: the number of fatal cases
            - Recovered <int>: the number of recovered cases
        @population <int/dict>: initial value of total population in the place
        @country <str>: country name
        @province <str>: province name
        """
        sr_data = SRData(clean_df, country=country, province=province)
        df = sr_data.make(population)
        dates = [date_obj.strftime(self.DATE_FORMAT) for date_obj in df.index]
        return dates

    def _read_population_data(self, dates, population, change_dict=None):
        """
        Make population dictionary easy to use in this class.
        @dates <list[str]>: list of dates, like 22Jan2020
        @population <int/dict>: initial value of total population in the place
        @change_dict <dict[str]=int/None>:
            - dictionary of total population
                - key: start date of population change
                - value: total population
        @return <dict[str]=int>:
            - key: date, like 22Jan2020
            - value: total population on the date
        """
        change_dict = dict() if change_dict is None else change_dict.copy()
        population_now = population
        pop_dict = dict()
        for date in dates:
            if date in change_dict.keys():
                population_now = change_dict[date]
            pop_dict[date] = population_now
        return pop_dict

    def run(self, n_points, min_duration=7,
            timeout=60, n_trials_iteration=10, n_jobs=-1):
        """
        Run optimization.
        @n_points <int>: the number of change points
        @min_duration <int>: minimum duration of one phase [days]
        @timeout <int>: time-out of run
        @n_trials_iteration <int>: the number of trials in one iteration
        @n_jobs <int>: the number of parallel jobs or -1 (CPU count)
        @return self
        """
        self.n_points = n_points
        self.min_duration = min_duration
        start_time = datetime.now()
        if n_points <= 0:
            self.run_time = 0
            self.total_trials = 0
            return self
        if self.study is None:
            self.study = optuna.create_study(
                direction="minimize"
            )
        print("Finding change points of S-R trend...")
        while True:
            self.study.optimize(
                lambda x: self.objective(x),
                n_trials=n_trials_iteration,
                n_jobs=n_jobs
            )
            # Check whether the change points are fixed or not
            if set(self.change_dates) == set(self.change_dates_previous):
                break
            # Check time-out and show cummurative run-time
            end_time = datetime.now()
            self.run_time += (end_time - start_time).total_seconds()
            minutes, seconds = divmod(int(self.run_time), 60)
            self.total_trials = len(self.study.trials)
            if self.run_time > timeout:
                print(
                    f"\rFinished {self.total_trials} trials in {minutes} min {seconds} sec.\n",
                    end=str()
                )
                break
            print(
                f"\rPerformed {self.total_trials} trials in {minutes} min {seconds} sec.",
                end=str()
            )
            self.change_dates_previous = self.change_dates[:]
        return self

    def objective(self, trial):
        """
        Objective function of Optuna study.
        This defines the parameter values using Optuna.
        @trial <optuna.trial>: a trial of the study
        @return <float>: score of the error function to minimize
        """
        # Suggest change points
        id_selected = [len(self.dates) - 1]
        for i in range(self.n_points):
            id_min = self.min_duration * (self.n_points - len(id_selected) + 1)
            id_max = id_selected[-1] - self.min_duration
            if id_min + self.min_duration > id_max:
                return np.inf
            id_new = trial.suggest_int(str(i), id_min, id_max)
            id_selected.append(id_new)
        self.change_dates = [
            self.dates[num] for num in sorted(id_selected[1:])
        ]
        # Calculate the start/end date of the phases
        start_dates, end_dates = self.phase_range(self.change_dates)
        return self.error_f(start_dates, end_dates)

    def phase_range(self, change_dates):
        """
        Return the start date and end date of the phases.
        @change_dates <list[str]>: list of change points, like 22Jan2020
        @return <tuple(list[str], list[str])>:
            - list of start dates
            - list of end dates
        """
        start_dates = [self.dates[0], *change_dates]
        end_dates_without_last = [
            (
                datetime.strptime(date, self.DATE_FORMAT) - timedelta(days=1)
            ).strftime(self.DATE_FORMAT)
            for date in change_dates
        ]
        end_dates = [*end_dates_without_last, self.dates[-1]]
        return (start_dates, end_dates)

    def error_f(self, start_dates, end_dates):
        """
        Definition of error score to minimize in the study.
        This is weghtend average of RMSLE scores.
        @start_dates <list[str]>: list of start date of phases (candidates)
        @end_dates <list[str]>: list of end date of phases (candidates)
        @return <float> : score of the error function to minimize
        """
        scores = list()
        for (start_date, end_date) in zip(start_dates, end_dates):
            population = self.pop_dict[start_date]
            trend = Trend(
                self.clean_df, population, self.country, province=self.province,
                start_date=start_date, end_date=end_date
            )
            trend.analyse()
            scores.append(trend.rmsle())
        return np.average(scores, weights=range(1, len(scores) + 1))

    def show(self, filename=None):
        """
        show the result as a figure and return the change points.
        @show_figure <bool>:
            - if True, show the history as a pair-plot of parameters.
        @filename <str>: filename of the figure, or None (show figure)
        @return <dict[str]={str: str/int}>:
            - key: phase number, like 1th, 2nd,...
                - 0th (initial) phase will be removed
            - value: {
                'start_date': <str> start date of the phass,
                'end_date': <str> end date of the phase,
                'population': <int>: population value at the start date
            }
        """
        # Create phase dictionary
        start_dates, end_dates = self.phase_range(self.change_dates)
        pop_list = [self.pop_dict[date] for date in start_dates]
        phases = [self.num2str(num) for num in range(len(start_dates))]
        phase_dict = {
            phase: {
                "start_date": start_date,
                "end_date": end_date,
                "population": population
            }
            for (start_date, end_date, population, phase)
            in list(zip(start_dates, end_dates, pop_list, phases))[1:]
        }
        # Curve fitting
        df_list = list()
        zip_itr = zip(start_dates, end_dates, pop_list, phases)
        for (start_date, end_date, population, phase) in zip_itr:
            trend = Trend(
                self.clean_df, population, self.country, province=self.province,
                start_date=start_date, end_date=end_date
            )
            trend.analyse()
            df = trend.result()
            phase = phase.replace("0th", "Initial")
            df = df.rename({f"{self.S}{self.P}": f"{phase}{self.P}"}, axis=1)
            df = df.rename({f"{self.S}{self.A}": f"{phase}{self.A}"}, axis=1)
            df = df.rename({f"{self.R}": f"{phase}_{self.R}"}, axis=1)
            df_list.append(df)
        comp_df = pd.concat(df_list, axis=1)
        comp_df[self.R] = comp_df.fillna(0).loc[
            :, comp_df.columns.str.endswith(self.R)
        ].sum(axis=1)
        comp_df[f"{self.S}{self.A}"] = comp_df.fillna(0).loc[
            :, comp_df.columns.str.endswith(self.A)
        ].sum(axis=1)
        comp_df = comp_df.apply(
            lambda x: pd.to_numeric(x, errors="coerce", downcast="integer"),
            axis=0
        )
        # Show figure
        pred_cols = comp_df.loc[
            :, comp_df.columns.str.endswith(self.P)
        ].columns.tolist()
        if len(pred_cols) == 1:
            title = f"{self.name}: S-R trend without change points"
        else:
            change_str = ", ".join(self.change_dates)
            title = f"{self.name}: S-R trend changed on {change_str}"
        Trend.show_with_many(
            result_df=comp_df,
            predicted_cols=pred_cols,
            title=title,
            filename=filename
        )
        return phase_dict