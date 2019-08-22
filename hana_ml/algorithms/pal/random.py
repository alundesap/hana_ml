"""
This module contains wrappers for PAL Random distribution sampling algorithms.

The following distribution functions are available:

    * :func:`bernoulli`
    * :func:`beta`
    * :func:`binomial`
    * :func:`cauchy`
    * :func:`chi_squared`
    * :func:`exponential`
    * :func:`gumbel`
    * :func:`f`
    * :func:`gamma`
    * :func:`geometric`
    * :func:`lognormal`
    * :func:`negative_binomial`
    * :func:`normal`
    * :func:`pert`
    * :func:`poisson`
    * :func:`student_t`
    * :func:`uniform`
    * :func:`weibull`
    * :func:`multinomial`
"""

# pylint: disable=too-many-lines, invalid-name
import logging
import uuid

from hdbcli import dbapi
from .pal_base import (
    Table,
    ParameterTable,
    DOUBLE,
    NVARCHAR,
    arg,
    create,
    try_drop,
    call_pal_auto,
    require_pal_usable,
)

logger = logging.getLogger(__name__)#pylint: disable=invalid-name

def _rds(conn_context, dist_params, num_random, seed, thread_ratio):#pylint: disable=too-many-locals
    require_pal_usable(conn_context)
    num_random = arg('num_random', num_random, int)
    seed = arg('seed', seed, int)
    thread_ratio = arg('thread_ratio', thread_ratio, float)
    if num_random < 0:
        msg = 'Parameter num_random should be greater than or equal to zero.'
        logger.error(msg)
        raise ValueError(msg)
    unique_id = str(uuid.uuid1()).replace('-', '_').upper()
    dist_name = dict(dist_params)['DISTRIBUTIONNAME']
    tables = ['#{}_{}_{}'.format(dist_name, tbl_name, unique_id) for tbl_name in
              ['DISTRIBUTION_PARAMETER', 'PARAMETER', 'RESULT']]
    dist_param_tbl, general_param_tbl, res_tbl = tables
    dist_param_spec = [('NAME', NVARCHAR(100)), ('VALUE', NVARCHAR(100))]
    general_params = [('NUM_RANDOM', num_random, None, None),
                      ('SEED', seed, None, None),
                      ('THREAD_RATIO', None, thread_ratio, None)]

    try:
        create(conn_context, Table(dist_param_tbl, dist_param_spec).with_data(dist_params))
        call_pal_auto(conn_context, 'PAL_DISTRIBUTION_RANDOM', conn_context.table(dist_param_tbl),
                      ParameterTable(general_param_tbl).with_data(general_params),
                      res_tbl)
    except dbapi.Error as db_err:
        logger.exception(str(db_err))
        try_drop(conn_context, tables)
        raise
    return conn_context.table(res_tbl)

#For now PAL only supports multinomial, there is no point doing any
#abstraction. Maybe later if other multivariate sampling algorithms like:
#multivariate normal is supported, then we can add it.
def multinomial(conn_context, n, pvals, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments, too-many-locals
    """
    Draw samples from a multinomial distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    n : int

        Number of trials.

    pvals : tuple of float and int

        Success fractions of each category.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - Generated random number columns, named by appending index number
            (starting from 1 to length of `pvals`) to ``Random_P``,
            type DOUBLE. There will be as many columns here as there are values
            in ``pvals``.

    Examples
    --------

    Draw samples from a multinomial distribution.

    >>> res = multinomial(cc, n=10, pvals=(0.1, 0.2, 0.3, 0.4), num_random=10)
    >>> res.collect()
       ID  RANDOM_P1  RANDOM_P2  RANDOM_P3  RANDOM_P4
    0   0        1.0        2.0        2.0        5.0
    1   1        1.0        2.0        3.0        4.0
    2   2        0.0        0.0        8.0        2.0
    3   3        0.0        2.0        1.0        7.0
    4   4        1.0        1.0        4.0        4.0
    5   5        1.0        1.0        4.0        4.0
    6   6        1.0        2.0        3.0        4.0
    7   7        1.0        4.0        2.0        3.0
    8   8        1.0        2.0        3.0        4.0
    9   9        4.0        1.0        1.0        4.0
    """
    require_pal_usable(conn_context)
    n = arg('n', n, int, True)
    pvals = arg('pvals', pvals, tuple, True)
    if any((not isinstance(pval, (float, int)) or pval < 0) for pval in pvals):
        msg = ('Parameter pvals should be a tuple of non-negative floats ' +
               'and ints.')
        logger.error(msg)
        raise ValueError(msg)
    num_random = arg('num_random', num_random, int)
    seed = arg('seed', seed, int)
    thread_ratio = arg('thread_ratio', thread_ratio, float)
    if num_random < 0:
        msg = 'Parameter num_random should be greater than or equal to zero.'
        logger.error(msg)
        raise ValueError(msg)
    unique_id = str(uuid.uuid1()).replace('-', '_').upper()
    tables = ['#MULTINOMIAL_{}_{}'.format(tbl_name, unique_id) for tbl_name in
              ['DISTRIBUTION_PARAMETER', 'PARAMETER', 'RESULT']]
    dist_param_tbl, general_param_tbl, res_tbl = tables
    dist_param_spec = [('TRIALS', NVARCHAR(100))]
    dist_param_spec.extend([('P{}'.format(str(i + 1)), DOUBLE) for i in range(len(pvals))])
    dist_param_data = [(n,) + pvals]
    general_params = [('DISTRIBUTIONNAME', None, None, 'MULTINOMIAL'),
                      ('NUM_RANDOM', num_random, None, None),
                      ('SEED', seed, None, None),
                      ('THREAD_RATIO', None, thread_ratio, None)]

    try:
        create(conn_context, Table(dist_param_tbl, dist_param_spec).with_data(dist_param_data))
        call_pal_auto(conn_context, 'PAL_DISTRIBUTION_RANDOM_MULTIVARIATE',
                      conn_context.table(dist_param_tbl),
                      ParameterTable(general_param_tbl).with_data(general_params),
                      res_tbl)
    except dbapi.Error as db_err:
        logger.exception(str(db_err))
        try_drop(conn_context, tables)
        raise
    return conn_context.table(res_tbl)

def bernoulli(conn_context, p=0.5, num_random=100, seed=None, thread_ratio=None):
    """
    Draw samples from a Bernoulli distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    p : float, optional

        Success fraction. The value range is from 0 to 1.

        Defaults to 0.5.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------
    Draw samples from a bernoulli distribution.

    >>> res = bernoulli(cc, p=0.5, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0               0.0
    1   1               0.0
    2   2               1.0
    3   3               1.0
    4   4               0.0
    5   5               1.0
    6   6               1.0
    7   7               0.0
    8   8               1.0
    9   9               0.0
    """
    p = arg('p', p, float)
    if p < 0 or p > 1:
        msg = 'Parameter p should be in the range of 0 and 1.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'BERNOULLI'),
                  ('SUCCESS_FRACTION', p)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def beta(conn_context, a=0.5, b=0.5, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a Beta distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    a : float, optional

        Alpha value, positive.

        Defaults to 0.5.

    b : float, optional

        Beta value, positive.

        Defaults to 0.5.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a beta distribution.

    >>> res = beta(cc, a=0.5, b=0.5, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.976130
    1   1          0.308346
    2   2          0.853118
    3   3          0.958553
    4   4          0.677258
    5   5          0.489628
    6   6          0.027733
    7   7          0.278073
    8   8          0.850181
    9   9          0.976244
    """
    a = arg('a', a, float)
    b = arg('b', b, float)
    if any(x <= 0 for x in (a, b)):
        msg = 'Parameters a and b should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'BETA'),
                  ('SHAPE1', a),
                  ('SHAPE2', b)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def binomial(conn_context, n=1, p=0.5, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a binomial distribution.



    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    n : int, optional

        Number of trials.

        Defaults to 1.

    p : float, optional

        Successful fraction. The value range is from 0 to 1.

        Defaults to 0.5.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.
    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a binomial distribution.

    >>> res = binomial(cc, n=1, p=0.5, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0               1.0
    1   1               1.0
    2   2               0.0
    3   3               1.0
    4   4               1.0
    5   5               1.0
    6   6               0.0
    7   7               1.0
    8   8               0.0
    9   9               1.0
    """
    p = arg('p', p, float)
    n = arg('n', n, int)
    if p < 0 or p > 1:
        msg = 'Parameter p should be in the range of 0 and 1.'
        logger.error(msg)
        raise ValueError(msg)
    if n < 0:
        msg = 'Parameter n should be at least zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'BINOMIAL'),
                  ('SUCCESS_FRACTION', p),
                  ('TRIALS', n)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def cauchy(conn_context, location=0, scale=1, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a cauchy distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    location : float, optional

        Defaults to 0.

    scale : float, optional

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a cauchy distribution.

    >>> res = cauchy(cc, location=0, scale=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          1.827259
    1   1         -1.877612
    2   2        -18.241436
    3   3         -1.216243
    4   4          2.091336
    5   5       -317.131147
    6   6         -2.804251
    7   7         -0.338566
    8   8          0.143280
    9   9          1.277245
    """
    location = arg('location', location, float)
    scale = arg('scale', scale, float)
    if scale <= 0:
        msg = 'Parameter scale should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'CAUCHY'),
                  ('LOCATION', location),
                  ('SCALE', scale)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def chi_squared(conn_context, dof=1, num_random=100, seed=None, thread_ratio=None):
    """
    Draw samples from a chi_squared distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    dof : int, optional

        Degrees of freedom.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:
          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a chi_squared distribution.

    >>> res = chi_squared(cc, dof=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.040571
    1   1          2.680756
    2   2          1.119563
    3   3          1.174072
    4   4          0.872421
    5   5          0.327169
    6   6          1.113164
    7   7          1.549585
    8   8          0.013953
    9   9          0.011735
    """
    dof = arg('dof', dof, int)
    if dof <= 0:
        msg = 'Parameter dof should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'CHI_SQUARED'),
                  ('DEGREES_OF_FREEDOM', dof)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def exponential(conn_context, lamb=1, num_random=100, seed=None, thread_ratio=None):
    """
    Draw samples from an exponential distribution.

    Parameters
    ----------

    conn_context : ConnectionContext
        Database connection object.

    lamb : float, optional

        The rate parameter, which is the inverse of the scale parameter.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from an exponential distribution.

    >>> res = exponential(cc, scale=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.035207
    1   1          0.559248
    2   2          0.122307
    3   3          2.339937
    4   4          1.130033
    5   5          0.985565
    6   6          0.030138
    7   7          0.231040
    8   8          1.233268
    9   9          0.876022
    """
    lamb = arg('lamb', lamb, float)
    if lamb <= 0:
        msg = 'Parameter lamb should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'EXPONENTIAL'),
                  ('RATE', lamb)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def gumbel(conn_context, location=0, scale=1, num_random=100, seed=None,# pylint: disable=too-many-arguments
           thread_ratio=None):
    """
    Draw samples from a Gumbel distribution, which is one of a class of
    Generalized Extreme Value (GEV) distributions used in modeling
    extreme value problems.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    location : float, optional

        Defaults to 0.

    scale : float, optional

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a gumbel distribution.

    >>> res = gumbel(cc, location=0, scale=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          1.544054
    1   1          0.339531
    2   2          0.394224
    3   3          3.161123
    4   4          1.208050
    5   5         -0.276447
    6   6          1.694589
    7   7          1.406419
    8   8         -0.443717
    9   9          0.156404
    """
    location = arg('location', location, float)
    scale = arg('scale', scale, float)
    if scale <= 0:
        msg = 'Parameter scale should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'EXTREME_VALUE'),
                  ('LOCATION', location),
                  ('SCALE', scale)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def f(conn_context, dof1=1, dof2=1, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments, invalid-name
    """
    Draw samples from an f distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    dof1 : int, optional

        DEGREES_OF_FREEDOM1.

        Defaults to 1.

    dof2 : int, optional

        DEGREES_OF_FREEDOM2.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::
            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------
    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a f distribution.

    >>> res = f(cc, dof1=1, dof2=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          6.494985
    1   1          0.054830
    2   2          0.752216
    3   3          4.946226
    4   4          0.167151
    5   5        351.789925
    6   6          0.810973
    7   7          0.362714
    8   8          0.019763
    9   9         10.553533
    """
    dof1 = arg('dof1', dof1, float)
    dof2 = arg('dof2', dof2, float)
    if any(dof <= 0 for dof in (dof1, dof2)):
        msg = 'Parameters dof1 and dof2 should be positive.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'FISHER_F'),
                  ('DEGREES_OF_FREEDOM1', dof1),
                  ('DEGREES_OF_FREEDOM2', dof2)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def gamma(conn_context, shape=1, scale=1, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a gamma distribution.

    Parameters
    ----------
    conn_context : ConnectionContext

        Database connection object.

    shape : float, optional

        Defaults to 1.

    scale : float, optional

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value remains
            the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------
    Draw samples from a gamma distribution.

    >>> res = gamma(cc, shape=1, scale=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.082794
    1   1          0.084031
    2   2          0.159490
    3   3          1.063100
    4   4          0.530218
    5   5          1.307313
    6   6          0.565527
    7   7          0.474969
    8   8          0.440999
    9   9          0.463645
    """
    shape = arg('shape', shape, float)
    scale = arg('scale', scale, float)
    if any(x <= 0 for x in (shape, scale)):
        msg = 'Parameters shape and scale should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'GAMMA'),
                  ('SHAPE', shape),
                  ('SCALE', scale)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def geometric(conn_context, p=0.5, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a geometric distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    p : float, optional

        Successful fraction. The value range is from 0 to 1.

        Defaults to 0.5.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:
          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a geometric distribution.

    >>> res = geometric(cc, p=0.5, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0               1.0
    1   1               1.0
    2   2               1.0
    3   3               0.0
    4   4               1.0
    5   5               0.0
    6   6               0.0
    7   7               0.0
    8   8               0.0
    9   9               0.0
    """
    p = arg('p', p, float)
    if p < 0 or p > 1:
        msg = 'Parameter p should be in the range of 0 and 1'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'GEOMETRIC'),
                  ('SUCCESS_FRACTION', p)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def lognormal(conn_context, mean=0, sigma=1, num_random=100, seed=None,# pylint: disable=too-many-arguments
              thread_ratio=None):
    """
    Draw samples from a lognormal distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    mean : float, optional

        Mean value of the underlying normal distribution.

        Defaults to 0.

    sigma : float, optional

        Standard deviation of the underlying normal distribution.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------
    Draw samples from a lognormal distribution.

    >>> res = lognormal(cc, mean=0, sigma=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.461803
    1   1          0.548432
    2   2          0.625874
    3   3          3.038529
    4   4          3.582703
    5   5          1.867543
    6   6          1.853857
    7   7          0.378827
    8   8          1.104031
    9   9          0.840102
    """
    mean = arg('mean', mean, float)
    sigma = arg('sigma', sigma, float)
    if sigma <= 0:
        msg = 'Parameter sigma should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'LOGNORMAL'),
                  ('LOCATION', mean),
                  ('SCALE', sigma)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

#Parameter n is related to the sucess number, and it should be int.
#However PAL also accepts float, and truncates it as int.
def negative_binomial(conn_context, n=1, p=0.5, num_random=100, seed=None,# pylint: disable=too-many-arguments
                      thread_ratio=None):
    """
    Draw samples from a negative_binomial distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    n : int, optional

        Number of successes.

        Defaults to 1.

    p : float, optional

        Successful fraction. The value range is from 0 to 1.

        Defaults to 0.5.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame
        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a negative_binomial distribution.

    >>> res = negative_binomial(cc, n=1, p=0.5, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0               0.0
    1   1               2.0
    2   2               3.0
    3   3               1.0
    4   4               1.0
    5   5               0.0
    6   6               2.0
    7   7               1.0
    8   8               2.0
    9   9               3.0
    """
    n = arg('n', n, (int, float))
    if n is not None:
        n = int(n)
    p = arg('p', p, float)
    if n <= 0:
        msg = 'Parameter n should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    if p < 0 or p > 1:
        msg = 'Parameter p should be in the range of 0 and 1.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'NEGATIVE_BINOMIAL'),
                  ('SUCCESSES', n),
                  ('SUCCESS_FRACTION', p)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def normal(conn_context, mean=0, sigma=None, variance=None, num_random=100,# pylint: disable=too-many-arguments
           seed=None, thread_ratio=None):
    """
    Draw samples from a normal distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    mean : float, optional

        Mean value.

        Defaults to 0.

    sigma : float, optional

        Standard deviation. It cannot be used together with `variance`.

        Defaults to 1.

    variance : float, optional

        Variance. It cannot be used together with `sigma`.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

            - 0: Uses the system time.
            - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

            - ID, type INTEGER, ID column.
            - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a normal distribution.

    >>> res = normal(cc, mean=0, sigma=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.321078
    1   1         -1.327626
    2   2          0.798867
    3   3         -0.116128
    4   4         -0.213519
    5   5          0.008566
    6   6          0.251733
    7   7          0.404510
    8   8         -0.534899
    9   9         -0.420968
    """
    mean = arg('mean', mean, float)
    sigma = arg('sigma', sigma, float)
    variance = arg('variance', variance, float)
    if sigma is not None and variance is not None:
        msg = ('Parameters variance and sigma cannot be used together. ' +
               'Please choose one from them.')
        logger.error(msg)
        raise ValueError(msg)
    if sigma <= 0:
        msg = 'Parameter sigma should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'NORMAL'),
                  ('MEAN', mean),
                  ('VARIANCE', variance),
                  ('SD', sigma)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def pert(conn_context, minimum=-1, mode=0, maximum=1, scale=4,# pylint: disable=too-many-arguments
         num_random=100, seed=None, thread_ratio=None):
    """
    Draw samples from a PERT distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    minimum : int, optional

        Minimum value.

        Defaults to -1.

    mode : float, optional

        Most likely value.

        Defaults to 0.

    maximum : float, optional

        Maximum value.

        Defaults to 1.

    scale : float, optional

        Defaults to 4.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a pert distribution.

    >>> res = pert(cc, minimum=-1, mode=0, maximum=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.360781
    1   1         -0.023649
    2   2          0.106465
    3   3          0.307412
    4   4         -0.136838
    5   5         -0.086010
    6   6         -0.504639
    7   7          0.335352
    8   8         -0.287202
    9   9          0.468597
    """
    minimum = arg('minimum', minimum, float)
    mode = arg('mode', mode, float)
    maximum = arg('maximum', maximum, float)
    scale = arg('scale', scale, float)
    # MIN < MODE < MAX
    if sorted([minimum, mode, maximum]) != [minimum, mode, maximum]:
        msg = ('minimum should be less than or equal to mode, ' +
               'and mode should be less than or equal to maximum.')
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'PERT'),
                  ('MIN', minimum),
                  ('MODE', mode),
                  ('MAX', maximum),
                  ('SCALE', scale)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def poisson(conn_context, theta=1.0, num_random=100, seed=None, thread_ratio=None):
    """
    Draw samples from a poisson distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    theta : float, optional

        The average number of events in an interval.

        Defaults to 1.0.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a poisson distribution.

    >>> res = poisson(cc, theta=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0               0.0
    1   1               1.0
    2   2               1.0
    3   3               1.0
    4   4               1.0
    5   5               1.0
    6   6               0.0
    7   7               2.0
    8   8               0.0
    9   9               1.0
    """
    theta = arg('theta', theta, float)
    if theta <= 0:
        msg = 'Parameter theta should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'POISSON'),
                  ('THETA', theta)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def student_t(conn_context, dof=1, num_random=100, seed=None, thread_ratio=None):
    """
    Draw samples from a Student's t-distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    dof : float, optional

        Degrees of freedom.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a Student's t-distribution.

    >>> res = student_t(cc, dof=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0         -0.433802
    1   1          1.972038
    2   2         -1.097313
    3   3         -0.225812
    4   4         -0.452342
    5   5          2.242921
    6   6          0.377288
    7   7          0.322347
    8   8          1.104877
    9   9         -0.017830
    """
    dof = arg('dof', dof, float)
    if dof <= 0:
        msg = 'Parameter dof should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'STUDENT_T'),
                  ('DEGREES_OF_FREEDOM', dof)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def uniform(conn_context, low=0, high=1, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a uniform distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    low : float, optional

        The lower bound.

        Defaults to 0.

    high : float, optional
        The upper bound.

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional

        Indicates the seed used to initialize the random number generator:

          - 0: Uses the system time.
          - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------

    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

          - ID, type INTEGER, ID column.
          - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a uniform distribution.

    >>> res = uniform(cc, low=-1, high=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          0.032920
    1   1          0.201923
    2   2          0.823313
    3   3         -0.495260
    4   4         -0.138329
    5   5          0.677732
    6   6          0.685200
    7   7          0.363627
    8   8          0.024849
    9   9         -0.441779
    """
    low = arg('low', low, float)
    high = arg('high', high, float)
    if low >= high:
        msg = 'Value of low should be lower than high.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'UNIFORM'),
                  ('MIN', low),
                  ('MAX', high)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)

def weibull(conn_context, shape=1, scale=1, num_random=100, seed=None, thread_ratio=None):# pylint: disable=too-many-arguments
    """
    Draw samples from a weibull distribution.

    Parameters
    ----------

    conn_context : ConnectionContext

        Database connection object.

    shape : float, optional

        Defaults to 1.

    scales : float, optional

        Defaults to 1.

    num_random : int, optional

        Specifies the number of random data to be generated.

        Defaults to 100.

    seed : int, optional
        Indicates the seed used to initialize the random number generator:

            - 0: Uses the system time.
            - Not 0: Uses the specified seed.

        .. note ::

            When multithreading is enabled, the random number sequences
            of different runs might be different even if the SEED value
            remains the same.

        Defaults to 0.

    thread_ratio : float, optional

        Controls the proportion of available threads to use.
        The value range is from 0 to 1, where 0 indicates a single thread,
        and 1 indicates up to all available threads. Values between 0 and 1
        will use that percentage of available threads. Values outside this
        range tell PAL to heuristically determine the number of threads to use.

        Defaults to 0.

    Returns
    -------
    res_df : DataFrame

        Dataframe containing the generated random samples,
        structured as follows:

            - ID, type INTEGER, ID column.
            - GENERATED_NUMBER, type DOUBLE, sample value.

    Examples
    --------

    Draw samples from a weibull distribution.

    >>> res = weibull(cc, shape=1, scale=1, num_random=10)
    >>> res.collect()
       ID  GENERATED_NUMBER
    0   0          2.188750
    1   1          0.247628
    2   2          0.339884
    3   3          0.902187
    4   4          0.909629
    5   5          0.514740
    6   6          4.627877
    7   7          0.143767
    8   8          0.847514
    9   9          2.368169
    """
    shape = arg('shape', shape, float)
    scale = arg('scale', scale, float)
    if shape <= 0 or scale <= 0:
        msg = 'Parameters shape and scale should be greater than zero.'
        logger.error(msg)
        raise ValueError(msg)
    dist_param = [('DISTRIBUTIONNAME', 'WEIBULL'),
                  ('SHAPE', shape),
                  ('SCALE', scale)]
    return _rds(conn_context, dist_param, num_random, seed, thread_ratio)
