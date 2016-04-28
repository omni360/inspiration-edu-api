import inspect
from functools import wraps

from django.utils.decorators import available_attrs


def should_check_action(actions_tested=[]):
    '''
    Decorator that receives the actions that this method tests and returns
    the function IFF all of the actions are actions that should be checked
    by the class.
    '''

    # Foolproof-ing in case the user forgot the ',' at the end of the actions
    # tuple. If we didn't have this, than the action won't be found because the
    # for-loop will iterate over the action's characters instead of over the
    # tuple with just the one action.
    if isinstance(actions_tested, basestring):
        actions_tested = [actions_tested]

    def decorator(test_func):
        @wraps(test_func, assigned=available_attrs(test_func))
        def _wrapped_test(*args, **kwargs):

            self = args[0]
            for action in actions_tested:
                if action not in self.actions:
                    return
            return test_func(*args, **kwargs)

        return _wrapped_test
    return decorator

