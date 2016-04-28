from .mixins import ApiListTestCase, ApiCreateTestCase, ApiRetrieveTestCase, ApiUpdateTestCase, ApiDeleteTestCase


class ApiListCreateTestCase(ApiListTestCase, ApiCreateTestCase):
    pass


class ApiRetrieveUpdateDeleteTestCase(ApiRetrieveTestCase, ApiUpdateTestCase, ApiDeleteTestCase):
    pass