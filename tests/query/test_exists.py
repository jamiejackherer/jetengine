from preggy import expect

from jetengine.query.exists import ExistsQueryOperator
from tests import AsyncTestCase


class TestExistsQueryOperator(AsyncTestCase):
    def test_to_query(self):
        query = ExistsQueryOperator()
        expect(query).not_to_be_null()
        expect(query.to_query("field_name", True)).to_be_like({"field_name": {"$exists": True}})
