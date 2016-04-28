from django.test.utils import CaptureQueriesContext
from django.db import DEFAULT_DB_ALIAS, connections

class _AssertCountQueriesContext(CaptureQueriesContext):
    """
    Test Context that lists the number of executed queries and counts them.

    Used by QueriesNumTestCase.
    """
    def __init__(self, test_case, connection):
        self.test_case = test_case
        super(_AssertCountQueriesContext, self).__init__(connection)

    def __exit__(self, exc_type, exc_value, traceback):
        super(_AssertCountQueriesContext, self).__exit__(exc_type, exc_value, traceback)
        if exc_type is not None:
            return
        self.executed = len(self)


class QueriesNumTestCase(object):
    """
    A Test Case mixin that provides additional asserts for measuring the 
    number of executed queries. 
    """

    def __runWithQueriesCountContext(self, func=None, *args, **kwargs):
        """Helper for running the tests in the context of the queries counter."""
        
        using = kwargs.pop("using", DEFAULT_DB_ALIAS)
        conn = connections[using]

        context = _AssertCountQueriesContext(self, conn)
        if func is None:
            return context

        with context:
            func(*args, **kwargs)

        return context

    def assertRangeQueries(self, accepted_range, func=None, *args, **kwargs):
        """Makes sure that number of executed queries is in range."""

        context = self.__runWithQueriesCountContext(func, *args, **kwargs)

        self.assertIn(context.executed, accepted_range)


